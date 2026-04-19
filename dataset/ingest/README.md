# dataset/ingest

Python layer for the companion dataset pipeline. Stages 1 through 4 in the
pipeline plan (Synthea generation, FHIR projection, format injection,
synthetic table generation) live here.

This directory is scaffolding only at the `chapter-01` tag. The modules
listed below are placeholders; their implementations land in Phases 3
through 6 of `docs/implementation_guide.md`.

```
src/ingest/
├── run_synthea.py         # Stage 1 — seeded Synthea invocation
├── fhir_to_staging/       # Stage 2 — one module per FHIR resource
├── format_injection/      # Stage 3 — epoch and string coercions
├── synthetic/             # Stage 4 — tables Synthea does not produce
└── load_bigquery.py       # bulk load to staging_bronze
tests/                     # projection and distribution tests
```

Install with `make install` from the repo root (which runs
`pip install -e dataset/ingest`).
