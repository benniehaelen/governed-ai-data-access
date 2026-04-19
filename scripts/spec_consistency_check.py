#!/usr/bin/env python3
"""Verify cross-references in spec/generated/ YAML.

Every reference in the generated YAML must resolve: rules mentioned in
tables must exist, tables mentioned in KPIs must exist, zones on tables
must be declared on their Data Product, and so on. This is the cheapest
gate you have against spec drift. It runs in seconds and catches the
kind of mistake (typo in a rule code, renamed table, removed data
product) that would otherwise surface twenty minutes into a dbt build.

Exits 0 if all checks pass, 1 otherwise. Suitable for CI.

Usage:

    python scripts/spec_consistency_check.py
    python scripts/spec_consistency_check.py --spec-dir path/to/generated
    python scripts/spec_consistency_check.py --strict   # warnings fail too
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import click
import yaml


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    check: str
    severity: str   # "error" or "warning"
    subject: str    # the record the violation belongs to (e.g. fqn, rule code)
    message: str


@dataclass
class Spec:
    tables: dict[str, dict]                  # keyed by "data_product.table"
    tables_by_name: dict[str, list[str]]     # bare table name -> list of fqns
    rules: dict[str, dict]                   # keyed by rule_code
    kpis: dict[str, dict]                    # keyed by metric_code (file stem)
    data_products: dict[str, dict]           # keyed by data_product name
    date_formats: set[str]                   # canonical storage_type names


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_spec(spec_dir: Path) -> Spec:
    if not spec_dir.exists():
        raise click.ClickException(
            f"spec directory {spec_dir} does not exist. "
            f"Run scripts/export_spec_to_yaml.py first."
        )

    tables: dict[str, dict] = {}
    tables_by_name: dict[str, list[str]] = {}
    tables_dir = spec_dir / "tables"
    if tables_dir.exists():
        for p in tables_dir.rglob("*.yaml"):
            data = yaml.safe_load(p.read_text())
            if not data or "data_product" not in data or "table" not in data:
                continue
            fqn = f"{data['data_product']}.{data['table']}"
            tables[fqn] = data
            tables_by_name.setdefault(data["table"], []).append(fqn)

    rules: dict[str, dict] = {}
    rules_dir = spec_dir / "business_rules"
    if rules_dir.exists():
        for p in rules_dir.rglob("*.yaml"):
            data = yaml.safe_load(p.read_text())
            if not data or "rule_code" not in data:
                continue
            rules[data["rule_code"]] = data

    kpis: dict[str, dict] = {}
    kpis_dir = spec_dir / "kpis"
    if kpis_dir.exists():
        for p in kpis_dir.rglob("*.yaml"):
            data = yaml.safe_load(p.read_text())
            if not data:
                continue
            kpis[p.stem] = data  # file stem is the Metric Code

    data_products: dict[str, dict] = {}
    dps_file = spec_dir / "data_products.yaml"
    if dps_file.exists():
        dps_data = yaml.safe_load(dps_file.read_text()) or {}
        for dp in dps_data.get("data_products", []):
            name = dp.get("data_product")
            if name:
                data_products[name] = dp

    date_formats: set[str] = set()
    dfc_file = spec_dir / "date_format_coverage.yaml"
    if dfc_file.exists():
        dfc_data = yaml.safe_load(dfc_file.read_text()) or {}
        for entry in dfc_data.get("storage_types", []):
            raw = str(entry.get("storage_type", "") or "")
            # Storage types may be multi-line (e.g. "DATE\n(Native DATE...)")
            first = raw.splitlines()[0].strip() if raw else ""
            if first:
                date_formats.add(first)

    return Spec(
        tables=tables,
        tables_by_name=tables_by_name,
        rules=rules,
        kpis=kpis,
        data_products=data_products,
        date_formats=date_formats,
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_table_rules_exist(spec: Spec) -> list[Violation]:
    """Rules named in a table's business_rules list must exist."""
    out: list[Violation] = []
    for fqn, table in spec.tables.items():
        for code in (table.get("business_rules") or []):
            if code not in spec.rules:
                out.append(Violation(
                    "table_rules_exist", "error", fqn,
                    f"references missing rule {code}",
                ))
    return out


def check_kpi_rules_exist(spec: Spec) -> list[Violation]:
    """Rules named in a KPI's rules_applied list must exist."""
    out: list[Violation] = []
    for code, kpi in spec.kpis.items():
        for rule_code in (kpi.get("rules_applied") or []):
            if rule_code not in spec.rules:
                out.append(Violation(
                    "kpi_rules_exist", "error", code,
                    f"references missing rule {rule_code}",
                ))
    return out


def check_kpi_tables_exist(spec: Spec) -> list[Violation]:
    """Tables named in a KPI's tables list must exist.

    KPI entries use bare table names (e.g. "readmission_index") rather than
    fully-qualified "data_product.table" references, so we match against
    tables_by_name. If a bare name is ambiguous (matches more than one Data
    Product) we also flag that: the spec sheet should disambiguate.
    """
    out: list[Violation] = []
    for code, kpi in spec.kpis.items():
        for name in (kpi.get("tables") or []):
            matches = spec.tables_by_name.get(name, [])
            if not matches:
                out.append(Violation(
                    "kpi_tables_exist", "error", code,
                    f"references missing table {name}",
                ))
            elif len(matches) > 1:
                out.append(Violation(
                    "kpi_tables_exist", "warning", code,
                    f"table name '{name}' is ambiguous across data products: {matches}",
                ))
    return out


def check_rule_applies_to(spec: Spec) -> list[Violation]:
    """Rule applies_to entries must be fully qualified and resolvable."""
    out: list[Violation] = []
    for code, rule in spec.rules.items():
        for ref in (rule.get("applies_to") or []):
            if "." not in ref:
                out.append(Violation(
                    "rule_applies_to", "error", code,
                    f"applies_to entry '{ref}' is not fully qualified (data_product.table)",
                ))
                continue
            if ref not in spec.tables:
                out.append(Violation(
                    "rule_applies_to", "error", code,
                    f"references missing table {ref}",
                ))
    return out


def check_table_data_product(spec: Spec) -> list[Violation]:
    """Every table's data_product must be declared."""
    out: list[Violation] = []
    for fqn, table in spec.tables.items():
        dp = table.get("data_product")
        if dp not in spec.data_products:
            out.append(Violation(
                "table_data_product", "error", fqn,
                f"unknown data_product '{dp}'",
            ))
    return out


def check_table_zone_declared(spec: Spec) -> list[Violation]:
    """A table's zone must appear in its Data Product's zones_present."""
    out: list[Violation] = []
    for fqn, table in spec.tables.items():
        zone = table.get("zone")
        dp = spec.data_products.get(table.get("data_product"))
        if dp is None:
            continue  # already caught by check_table_data_product
        declared = dp.get("zones_present") or []
        if zone not in declared:
            out.append(Violation(
                "table_zone_declared", "error", fqn,
                f"zone '{zone}' not declared in data_product.zones_present {declared}",
            ))
    return out


def check_preferred_zone(spec: Spec) -> list[Violation]:
    """Data Product preferred_zone must be in zones_present."""
    out: list[Violation] = []
    for name, dp in spec.data_products.items():
        preferred = dp.get("preferred_zone")
        present = dp.get("zones_present") or []
        if preferred is None:
            continue
        # gold_only etc. are strategies, not zones; only check zone-valued fields
        if preferred not in present:
            out.append(Violation(
                "preferred_zone", "error", name,
                f"preferred_zone '{preferred}' not in zones_present {present}",
            ))
    return out


def check_primary_key_present(spec: Spec) -> list[Violation]:
    """Every table must declare a primary key."""
    out: list[Violation] = []
    for fqn, table in spec.tables.items():
        pk = table.get("primary_key")
        if not pk:
            out.append(Violation(
                "primary_key_present", "error", fqn,
                "missing primary_key",
            ))
    return out


def check_date_storage_type(spec: Spec) -> list[Violation]:
    """If a table declares a date column, storage type should match the
    Date Format Coverage sheet. Warning-only: the Date Format sheet is an
    audit, not a hard contract, and some staging tables may carry formats
    that are not yet audited.
    """
    out: list[Violation] = []
    for fqn, table in spec.tables.items():
        date_col = table.get("date_column")
        storage = table.get("date_storage_type")
        if date_col and not storage:
            out.append(Violation(
                "date_storage_type", "warning", fqn,
                f"has date_column '{date_col}' but no date_storage_type",
            ))
        elif storage and spec.date_formats and storage not in spec.date_formats:
            out.append(Violation(
                "date_storage_type", "warning", fqn,
                f"date_storage_type '{storage}' not listed in Date Format Coverage sheet",
            ))
    return out


def check_fanout_note(spec: Spec) -> list[Violation]:
    """If fan_out_risk is 'yes', fan_out_note should be non-empty, because
    the note is what a future developer needs to avoid the naive-COUNT trap.
    """
    out: list[Violation] = []
    for fqn, table in spec.tables.items():
        risk = str(table.get("fan_out_risk") or "").lower()
        note = table.get("fan_out_note")
        if risk == "yes" and not note:
            out.append(Violation(
                "fanout_note", "warning", fqn,
                "fan_out_risk is 'yes' but fan_out_note is empty",
            ))
    return out


CHECKS: list[Callable[[Spec], list[Violation]]] = [
    check_table_rules_exist,
    check_kpi_rules_exist,
    check_kpi_tables_exist,
    check_rule_applies_to,
    check_table_data_product,
    check_table_zone_declared,
    check_preferred_zone,
    check_primary_key_present,
    check_date_storage_type,
    check_fanout_note,
]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(violations: list[Violation]) -> tuple[int, int]:
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    by_check: dict[str, list[Violation]] = {}
    for v in violations:
        by_check.setdefault(v.check, []).append(v)

    for check_name in sorted(by_check):
        vios = by_check[check_name]
        n_err = sum(1 for v in vios if v.severity == "error")
        n_warn = sum(1 for v in vios if v.severity == "warning")
        click.echo(f"[{check_name}]  {n_err} errors, {n_warn} warnings")
        for v in vios:
            marker = "ERROR" if v.severity == "error" else "WARN "
            click.echo(f"  {marker}  {v.subject}: {v.message}")
        click.echo("")

    return len(errors), len(warnings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--spec-dir",
    default="spec/generated",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory containing generated YAML.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors (CI gate).",
)
def main(spec_dir: Path, strict: bool) -> None:
    """Verify cross-references in spec/generated/."""
    click.echo(f"Loading spec from {spec_dir}")
    spec = load_spec(spec_dir)
    click.echo(
        f"  {len(spec.tables)} tables, {len(spec.rules)} rules, "
        f"{len(spec.kpis)} KPIs, {len(spec.data_products)} data products"
    )
    click.echo("")

    violations: list[Violation] = []
    for fn in CHECKS:
        violations.extend(fn(spec))

    if violations:
        n_err, n_warn = print_report(violations)
        click.echo(f"Totals: {n_err} errors, {n_warn} warnings")
        if n_err or (strict and n_warn):
            sys.exit(1)
    else:
        click.echo("All checks passed.")


if __name__ == "__main__":
    main()
