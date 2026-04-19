# governed-ai-data-access

Companion monorepo for the book **Governed AI Data Access**. Contains three
subsystems plus an evaluation harness that together produce the exact dataset
the book's examples reference, the retrieval-and-resolver layer the book
teaches how to build, and the authoring environment that owns the knowledge
graph and the metrics registry.

Everything that is cloneable and runnable from chapter to chapter lives here.

## Subsystems

```
dataset/          Python ingest + dbt transformation pipeline (Chapters 2, 7, 8, 9, 10)
mcp_server/       Nine-step query pipeline and governed resolvers (Chapters 3, 6-10)
studio/           Knowledge Graph Studio, browser-based authoring (Chapters 4-5)
evaluation/       Release-gate test harness spanning all three subsystems (Chapter 11)

spec/             Single source of truth: the dataset specification workbook
rules/            Business rules + metrics YAML, consumed by dataset and mcp_server
scripts/          Cross-subsystem utilities (spec export, consistency check, bootstrap)
docs/             Architecture, quickstart, chapter map, pipeline plan
```

The pipeline plan (`docs/Book_Data_Pipeline_Plan.docx`) is the authoritative
layout reference. The implementation guide (`docs/implementation_guide.md`)
is the phased, executable plan for building each subsystem.

## Where to start

| Role                           | Read first                                                  |
| ------------------------------ | ----------------------------------------------------------- |
| Book reader cloning at a tag   | `docs/chapter_map.md`, then the quickstart for your chapter |
| Contributor extending the repo | `docs/implementation_guide.md`                              |
| Reviewer evaluating scope      | `docs/Book_Data_Pipeline_Plan.docx`                         |
| Claude Code agent              | `CLAUDE.md`                                                 |

## What works today

At the `chapter-01` tag, only the spec export and consistency check are wired:

```bash
make help              # list all Makefile targets
make install           # pip install -e dataset/ingest plus dev deps
make spec-export       # Excel workbook -> spec/generated/*.yaml
make spec-check        # cross-reference validation; CI gate in strict mode
```

Phases 3 through 14 of `docs/implementation_guide.md` are stubbed in the
Makefile. Each stub fails loudly with a `NOT-YET-IMPLEMENTED` message pointing
back to the guide.

## Configuration

Every credential and project identifier comes from the environment, never the
repository. Set these before running anything that touches GCP:

```bash
export GCP_PROJECT=your-sandbox-project
export GCP_LOCATION=US
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/sa-key.json
```

Scale is selected in `dataset/config/dataset.yaml`. The three named scales —
`dev` (1k patients, under 5 min), `reader` (10k, ~$2), `canonical` (100k, ~$25) —
match Section 8 of the pipeline plan.

## Release tags and the golden-answer contract

Every chapter in the book corresponds to a git tag (`chapter-02`, `chapter-03`,
and so on). A tag captures the full monorepo state: dataset, MCP Server,
Studio, and evaluation harness together. Upgrading Synthea, dbt, the BigQuery
client, or any other pinned dependency invalidates the committed
`evaluation/golden_answers/kpi_snapshots.csv` and forces a regeneration pass.
This is intentional friction: the book is a long-lived artifact and silent
dependency drift is a real risk.

## A note on the data

Every patient, encounter, claim, facility, provider, and diagnosis in this
repository is synthetic. The patients come from Synthea with a fixed seed; the
supporting tables (schedule, coverage, formulary, adjustments) are generated
deterministically from seeds derived from module names. No real clinical
record is ever present. Do not use this dataset for any purpose other than
following the book's examples.

## Links

- Pipeline plan: [`docs/Book_Data_Pipeline_Plan.docx`](docs/Book_Data_Pipeline_Plan.docx)
- Implementation guide: [`docs/implementation_guide.md`](docs/implementation_guide.md)
- Chapter map: [`docs/chapter_map.md`](docs/chapter_map.md)
- Spec workbook: [`spec/Companion_Dataset_Specification.xlsx`](spec/Companion_Dataset_Specification.xlsx)
