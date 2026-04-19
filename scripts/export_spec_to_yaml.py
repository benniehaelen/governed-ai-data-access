#!/usr/bin/env python3
"""Export Companion_Dataset_Specification.xlsx into versioned YAML.

The workbook is the source of truth for the companion dataset. This script
is the one place in the repo that parses Excel; every downstream consumer
(dbt macros, codegen, the MCP Server, the evaluation harness) reads the
YAML produced here. Re-running the script is idempotent: identical input
yields identical output.

Outputs under `spec/generated/`:

    tables/<data_product>/<table>.yaml     one file per row in Tables
    business_rules/<RULE_CODE>.yaml        one file per row in Business Rules
    kpis/<METRIC_CODE>.yaml                one file per KPI (merged across
                                            the three sub-sections of the
                                            KPIs sheet)
    data_products.yaml                     all rows from Data Products
    date_format_coverage.yaml              all rows from Date Format Coverage
    resolver_coverage_matrix.yaml          all rows from Resolver Coverage Matrix

Each record carries a `_source_row` field pointing back to the 1-indexed
Excel row number for traceability during review.

Usage:

    python scripts/export_spec_to_yaml.py
    python scripts/export_spec_to_yaml.py --workbook path/to/spec.xlsx --out path/to/generated
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import click
import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Header row (0-indexed) on most sheets. The workbook shows this as Excel row 4.
HEADER_ROW = 3

# Columns parsed as bracketed lists: "[a, b, c]" -> ["a", "b", "c"].
BRACKETED_LIST_COLUMNS: set[tuple[str, str]] = {
    ("Tables", "Primary Key"),
    ("Business Rules", "Applies To"),
}

# Columns parsed as comma-separated lists: "a, b, c" -> ["a", "b", "c"].
COMMA_LIST_COLUMNS: set[tuple[str, str]] = {
    ("Tables", "Business Rules"),
    ("KPIs", "Rules Applied"),
    ("KPIs", "Tables"),
    ("KPIs", "Valid Dimensions"),
    ("Data Products", "Zones Present"),
}


# ---------------------------------------------------------------------------
# Value normalization
# ---------------------------------------------------------------------------

def snake_case(s: str) -> str:
    """Normalize a column header to a snake_case key.

    "Data Product"              -> "data_product"
    "Backstory (why it exists)" -> "backstory"
    "Min Met?"                  -> "min_met"
    "Owner / Version"           -> "owner_version"
    "Wrong Way #1"              -> "wrong_way_1"
    """
    s = str(s).strip()
    s = re.sub(r"\s*\([^)]*\)", "", s)            # drop parenthetical qualifiers
    s = s.rstrip("?.:")                            # strip trailing punctuation
    s = re.sub(r"[\s/\-#]+", "_", s)              # whitespace, slash, dash, hash -> underscore
    s = re.sub(r"[^A-Za-z0-9_]", "", s)           # drop anything else
    s = re.sub(r"_+", "_", s).strip("_")          # collapse and trim underscores
    return s.lower()


def _parse_bracketed_list(v: Any) -> list[str] | None:
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not (s.startswith("[") and s.endswith("]")):
        return [s] if s else []
    inner = s[1:-1].strip()
    return [x.strip() for x in inner.split(",") if x.strip()]


def _parse_comma_list(v: Any) -> list[str] | None:
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def clean_value(v: Any, sheet: str, col: str) -> Any:
    """Convert a single cell value to a YAML-friendly Python form."""
    if pd.isna(v):
        return None
    key = (sheet, col)
    if key in BRACKETED_LIST_COLUMNS:
        return _parse_bracketed_list(v)
    if key in COMMA_LIST_COLUMNS:
        return _parse_comma_list(v)
    if isinstance(v, str):
        # Authors occasionally embed the literal two-character sequence "\n"
        # in cells to force a line break. Convert to an actual newline so the
        # YAML block-literal style renders them correctly.
        return v.replace("\\n", "\n").strip()
    if hasattr(v, "item"):  # numpy scalar -> native Python
        return v.item()
    return v


def row_to_dict(row: pd.Series, sheet: str, excel_row: int) -> dict[str, Any]:
    """Convert a DataFrame row to an ordered dict keyed by snake_case names."""
    out: dict[str, Any] = {"_source_row": excel_row}
    for col in row.index:
        out[snake_case(str(col))] = clean_value(row[col], sheet, str(col))
    return out


def safe_filename(s: str) -> str:
    """Make a filesystem-safe filename component."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s).strip())


# ---------------------------------------------------------------------------
# YAML serializer
# ---------------------------------------------------------------------------

class _BlockDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences beneath their parent key."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow=flow, indentless=False)


def _str_presenter(dumper: yaml.Dumper, data: str) -> Any:
    """Render multi-line strings with the literal `|` style for readability."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_BlockDumper.add_representer(str, _str_presenter)


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=_BlockDumper,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=100,
        )


# ---------------------------------------------------------------------------
# Sheet readers
# ---------------------------------------------------------------------------

def _read_sheet(workbook: Path, sheet: str, header_row: int = HEADER_ROW) -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet, header=header_row)
    df = df.dropna(how="all").reset_index(drop=True)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.loc[:, df.columns.notna()]
    return df


def _excel_row_number(df_index: int, header_row_0_indexed: int = HEADER_ROW) -> int:
    """Convert a DataFrame row index back to the 1-indexed Excel row number.

    If the header sits at Excel row 4 (0-indexed row 3), the first data row
    is Excel row 5, which is DataFrame index 0. So Excel row = index + 5.
    """
    return df_index + header_row_0_indexed + 2


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------

def export_tables(workbook: Path, out_dir: Path) -> int:
    sheet = "Tables"
    df = _read_sheet(workbook, sheet)
    count = 0
    for i, row in df.iterrows():
        if pd.isna(row.get("Data Product")) or pd.isna(row.get("Table")):
            continue
        data = row_to_dict(row, sheet, _excel_row_number(int(i)))
        dp = safe_filename(row["Data Product"])
        table = safe_filename(row["Table"])
        write_yaml(out_dir / "tables" / dp / f"{table}.yaml", data)
        count += 1
    return count


def export_business_rules(workbook: Path, out_dir: Path) -> int:
    sheet = "Business Rules"
    df = _read_sheet(workbook, sheet)
    count = 0
    for i, row in df.iterrows():
        code = row.get("Rule Code")
        if pd.isna(code):
            continue
        data = row_to_dict(row, sheet, _excel_row_number(int(i)))
        write_yaml(out_dir / "business_rules" / f"{safe_filename(code)}.yaml", data)
        count += 1
    return count


def export_kpis(workbook: Path, out_dir: Path) -> int:
    """The KPIs sheet has three stacked sub-sections (canonical definitions,
    plausibly-wrong alternatives, certification and known-good answers), each
    with its own header row beginning with "Metric Code". This function
    locates all three headers, parses each section, and merges the rows
    keyed on Metric Code so that every KPI becomes a single YAML file with
    fields from all three sections.
    """
    sheet = "KPIs"
    raw = pd.read_excel(workbook, sheet_name=sheet, header=None)

    header_row_indices: list[int] = [
        i for i in range(len(raw))
        if (raw.iloc[i].astype(str).str.strip() == "Metric Code").any()
    ]
    if not header_row_indices:
        raise RuntimeError("No 'Metric Code' header rows found in the KPIs sheet.")

    merged: dict[str, dict[str, Any]] = {}

    for section_idx, hdr_i in enumerate(header_row_indices):
        end_i = (
            header_row_indices[section_idx + 1]
            if section_idx + 1 < len(header_row_indices)
            else len(raw)
        )
        header = raw.iloc[hdr_i].tolist()

        # Column positions for this section
        metric_code_col = next(
            (pos for pos, name in enumerate(header)
             if str(name).strip() == "Metric Code"),
            None,
        )
        if metric_code_col is None:
            continue

        for data_i in range(hdr_i + 1, end_i):
            row = raw.iloc[data_i]
            code = row.iloc[metric_code_col]
            if pd.isna(code):
                continue
            code_str = str(code).strip()
            if not code_str.startswith("METRIC_"):
                # Skip stray section sub-headers like "Certification and known-good answers"
                continue

            excel_row = data_i + 1  # 1-indexed Excel row

            if code_str not in merged:
                merged[code_str] = {"_source_row": excel_row}

            for pos, col_name in enumerate(header):
                if pd.isna(col_name):
                    continue
                col_name_str = str(col_name).strip()
                if col_name_str == "Metric Code":
                    continue
                val = clean_value(row.iloc[pos], sheet, col_name_str)
                if val is None:
                    continue
                merged[code_str][snake_case(col_name_str)] = val

    for code, data in merged.items():
        write_yaml(out_dir / "kpis" / f"{safe_filename(code)}.yaml", data)

    return len(merged)


def export_data_products(workbook: Path, out_dir: Path) -> int:
    sheet = "Data Products"
    df = _read_sheet(workbook, sheet)
    items: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        if pd.isna(row.get("Data Product")):
            continue
        items.append(row_to_dict(row, sheet, _excel_row_number(int(i))))
    write_yaml(out_dir / "data_products.yaml", {"data_products": items})
    return len(items)


def export_simple_sheet(
    workbook: Path,
    out_dir: Path,
    sheet: str,
    filename: str,
    list_key: str,
) -> int:
    df = _read_sheet(workbook, sheet)
    items: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        if row.dropna().empty:
            continue
        items.append(row_to_dict(row, sheet, _excel_row_number(int(i))))
    write_yaml(out_dir / filename, {list_key: items})
    return len(items)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--workbook",
    "workbook_path",
    default="spec/Companion_Dataset_Specification.xlsx",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the spec workbook.",
)
@click.option(
    "--out",
    "out_dir",
    default="spec/generated",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for generated YAML.",
)
@click.option(
    "--clean/--no-clean",
    default=True,
    help="Remove the output directory before writing (default: true).",
)
def main(workbook_path: Path, out_dir: Path, clean: bool) -> None:
    """Export the spec workbook into versioned YAML."""
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    click.echo(f"Reading  {workbook_path}")
    click.echo(f"Writing  {out_dir}")

    tables = export_tables(workbook_path, out_dir)
    rules = export_business_rules(workbook_path, out_dir)
    kpis = export_kpis(workbook_path, out_dir)
    dps = export_data_products(workbook_path, out_dir)
    dfc = export_simple_sheet(
        workbook_path, out_dir,
        "Date Format Coverage", "date_format_coverage.yaml", "storage_types",
    )
    rcm = export_simple_sheet(
        workbook_path, out_dir,
        "Resolver Coverage Matrix", "resolver_coverage_matrix.yaml", "resolver_patterns",
    )

    click.echo("")
    click.echo("Summary:")
    click.echo(f"  {tables:>3} tables")
    click.echo(f"  {rules:>3} business rules")
    click.echo(f"  {kpis:>3} KPIs")
    click.echo(f"  {dps:>3} data products")
    click.echo(f"  {dfc:>3} date format entries")
    click.echo(f"  {rcm:>3} resolver patterns")


if __name__ == "__main__":
    main()
