# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Companion repo for the "Governed AI Data Access" book. The dataset pipeline is built in phases (see `docs/implementation_guide.md`). **Only Phases 1-2 are implemented.** Phases 3-14 exist as Makefile stubs that fail loudly with `NOT-YET-IMPLEMENTED` messages. Do not invent scaffolding for later phases — follow the guide.

## Common commands

All work starts from the repo root. `make help` lists every target.

```bash
make install              # pip install deps into current venv
make spec-export          # workbook -> spec/generated/*.yaml
make spec-check           # export + cross-reference validation (main Phase 2 gate)
make spec-check-strict    # warnings fail too; this is what CI runs
make ci                   # local simulation of CI
make clean-spec           # rm -rf spec/generated
```

Run a single consistency check function: there is no built-in selector — edit the `CHECKS` list in `scripts/spec_consistency_check.py` or import individual `check_*` functions and call `load_spec(Path("spec/generated"))` in a REPL.

Running the export/check scripts directly:

```bash
python scripts/export_spec_to_yaml.py --workbook spec/Companion_Dataset_Specification.xlsx --out spec/generated
python scripts/spec_consistency_check.py --spec-dir spec/generated [--strict]
```

**Shell note:** this is Windows + bash. Use forward slashes and `/dev/null`, not `NUL`.

## Architecture

### The spec workbook is the contract

`spec/Companion_Dataset_Specification.xlsx` is the single source of truth for tables (41), business rules (20), KPIs (5), data products (6), date format coverage, and resolver coverage matrix. **Only `scripts/export_spec_to_yaml.py` parses Excel.** Everything downstream (future dbt macros, codegen, MCP server, eval harness) reads the generated YAML.

`spec/generated/` is a build artifact. Normally not committed, but checked in here so the repo is inspectable without running the pipeline. `make clean-spec` removes it; `make spec-export` rebuilds it. The Makefile uses a `.timestamp` file so `make spec-check` auto-re-exports when the workbook changes.

### Two-stage Phase 2 pipeline

1. **`export_spec_to_yaml.py`** — idempotent Excel→YAML converter. Key decisions:
   - Header row is Excel row 4 (`HEADER_ROW = 3`, 0-indexed).
   - Column normalization via `snake_case()` strips parentheticals, trailing punctuation, special chars.
   - Bracketed lists (`[a, b, c]`) vs comma lists are configured per `(sheet, column)` in `BRACKETED_LIST_COLUMNS` / `COMMA_LIST_COLUMNS`. Add new list columns there, not by heuristics.
   - Every record carries `_source_row` pointing back to the 1-indexed Excel row for traceability.
   - The **KPIs sheet is special**: three stacked sub-sections, each with its own `Metric Code` header row. `export_kpis()` finds all header rows, parses each section, and merges rows keyed on Metric Code so each KPI becomes one YAML file.
   - Multi-line strings are rendered with YAML literal-block style (`|`) via a custom `_BlockDumper`.
   - Authors sometimes embed the literal two-character sequence `\n` in cells; `clean_value()` converts these to real newlines.

2. **`spec_consistency_check.py`** — cross-reference gate. The `Spec` dataclass holds the loaded YAML; `CHECKS` is a list of ten `check_*` functions that return `Violation`s. Errors fail the run; warnings fail only under `--strict`. To add a check: write a `check_foo(spec) -> list[Violation]` function and append it to `CHECKS`. Note that KPIs reference tables by bare name (not `data_product.table`), so `check_kpi_tables_exist` uses `tables_by_name` and warns on ambiguity.

### Known state

Running `make spec-check` against the shipped workbook produces one **real error** in `METRIC_ED_DOOR_TO_PROVIDER`: the workbook's `Tables` cell reads `encounter (emergency type)` instead of `encounter`. Commit `c00078f` fixed this in the downstream model but the workbook cell itself may still need updating. Do not "fix" the checker to make it pass — fix the workbook cell.

## Guidance from the implementation guide (read before editing)

The guide explicitly lists things to refuse:

- **Do not rewrite the workbook's SQL fragments** to be "cleaner" or more idiomatic. The workbook is the contract; codegen must preserve it exactly (Phase 8).
- **Do not invent synthetic distributions.** Phase 6 requires an author-written `docs/synthetic_distributions.md` first.
- **Do not widen KPI evaluation tolerances** past 1% — that number is calibrated against `APPROX_QUANTILES` drift.
- **Do not add "helpful" dbt features** (incremental materializations, snapshots, extra tests) until Chapter 3 work begins.

When implementing later phases, one Data Product at a time. The diff-review workflow only works when diffs are small.

## What is deliberately not in the repo

- `dataset/`, `mcp_server/`, `studio/`, `evaluation/` directories — created during Phase 1 of the guide.
- Credentials. `GCP_PROJECT`, `GCP_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS` come from the user's environment (`.envrc` or shell), never committed.
- Synthea JAR and config — added in Phase 3 under `tools/synthea/`.
