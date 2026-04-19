# dataset/dbt

SQL transformation layer for the companion dataset pipeline. Stages 5 through 9
of the pipeline plan (bronze, silver, gold, quality reporting, KPIs) live here.

This directory is scaffolding at the `chapter-01` tag. `dbt_project.yml` and
`profiles.yml.template` are in place; model, macro, seed, and test folders are
empty.

## Layout

```
dbt_project.yml
profiles.yml.template          # copy to ~/.dbt/profiles.yml and fill in env vars
models/
  clinical_core/{bronze,silver,gold}/
  revenue_cycle/{silver,gold}/
  quality_reporting/gold/
  workforce/{silver,gold}/
  supply_chain/{bronze,silver,gold}/
  reference/gold/
  metrics/                     # codegen'd from rules/metrics YAML (Phase 8)
macros/
  business_rules/              # codegen'd from rules/business_rules YAML (Phase 8)
  date_format/                 # per-column date casts (Phase 7)
  recency/                     # dedup patterns (Phase 9)
seeds/                         # facility.csv, calendar_*.csv, terminology_registry.csv, etc.
tests/                         # project-level data tests (schema.yml lives beside models)
```

Zone subfolders come directly from `spec/generated/data_products.yaml`
`zones_present`. If a Data Product does not declare a zone in the workbook,
the subfolder does not exist.

## How to run

Not yet runnable. `make dbt-build` is wired in the root Makefile and will begin
producing tables once Phase 7 (project config) and Phases 9-10 (models) land.
