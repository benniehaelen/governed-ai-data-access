# governed-ai-data-access starter bundle

This bundle is the concrete starting point for the companion repository of
the "Governed AI Data Access" book. Files are already laid out to match
their target locations in the monorepo, so you can unzip into an empty
directory, `git init`, and proceed.

## What is in here

```
governed-ai-data-access-starter/
├── Makefile                                  # Phase 2 wired; later phases stubbed
├── docs/
│   ├── Book_Data_Pipeline_Plan.docx          # monorepo pipeline plan
│   └── implementation_guide.md               # phase-by-phase runbook
├── scripts/
│   ├── export_spec_to_yaml.py                # workbook → versioned YAML
│   └── spec_consistency_check.py             # cross-reference gate
└── spec/
    ├── Companion_Dataset_Specification.xlsx  # source of truth
    └── generated/                            # pre-generated YAML (see note below)
        ├── tables/<data_product>/*.yaml      # 41 table specs
        ├── business_rules/*.yaml             # 20 rules
        ├── kpis/*.yaml                       # 5 KPIs
        ├── data_products.yaml
        ├── date_format_coverage.yaml
        └── resolver_coverage_matrix.yaml
```

## Note on `spec/generated/`

The YAML under `spec/generated/` was produced by running
`scripts/export_spec_to_yaml.py` against the workbook and is included so
you can inspect the shape without running anything. Normally you would
not commit this directory; it is a build artifact derivable from the
workbook. `make clean-spec` removes it; `make spec-export` rebuilds it.

## First run

```bash
make help              # list all targets with descriptions
make spec-check        # exercise the Phase 2 pipeline end to end
```

The `spec-check` run against the workbook as shipped will surface one
real consistency error in `METRIC_ED_DOOR_TO_PROVIDER` (the `Tables`
column reads `encounter (emergency type)` instead of `encounter`). Fix
the cell in the workbook and the check passes clean. See the
implementation guide for context.

## Where to go from here

Open `docs/implementation_guide.md` and start at Phase 1. Phases 1 and 2
are the scaffolding and spec-export work. Everything in this bundle
supports those two phases; Phase 3 onward is wired into the Makefile as
stubs that will fail loudly until you implement them.

## What is deliberately not here

- `dataset/`, `mcp_server/`, `studio/`, `evaluation/` directories. These
  will appear as you execute Phase 1 of the implementation guide. The
  bundle stops at the files needed to kick off that work.
- `.envrc` or any credentials. You provide GCP_PROJECT, GCP_LOCATION,
  and a service-account key path through your own environment.
- Synthea JAR and config. Pin a version and drop it under
  `tools/synthea/` when you reach Phase 3.
