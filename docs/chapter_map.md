# Chapter map

This file records, for each book chapter, which monorepo directories and
spec tables the chapter primarily touches. It is the connective tissue
between the manuscript and the companion repository, and is updated as
each phase of `implementation_guide.md` completes.

Chapter-to-tag correspondence (from the pipeline plan, Section 9):

| Tag          | State of the repo                                              |
| ------------ | -------------------------------------------------------------- |
| `chapter-01` | Scaffolding only — this document, folder tree, spec export.    |
| `chapter-02` | Dataset pipeline complete; golden answers pinned.              |
| `chapter-03` | MCP Server retrieval layer in place.                           |
| `chapter-04` | Knowledge graph schema loaded; Studio read-only browsing.      |
| `chapter-05` | Metrics registry fully authored through the Studio.            |
| `chapter-06` | Nine-step query pipeline end to end, no resolvers yet.         |
| `chapter-07` | DateResolver wired.                                            |
| `chapter-08` | ZoneRouter wired; silver-vs-gold governance teaching material. |
| `chapter-09` | GrainResolver wired.                                           |
| `chapter-10` | BusinessRuleResolver wired.                                    |
| `chapter-11` | Evaluation harness complete; CI gates on golden answers.       |
| `chapter-14` | MLOps chapter — production deployment notes, not code.         |

## Chapter-to-directory map

| Chapter     | Primary directories touched                                                                              |
| ----------- | -------------------------------------------------------------------------------------------------------- |
| 1           | `docs/`, `README.md`                                                                                     |
| 2           | `dataset/ingest/`, `dataset/dbt/`, `spec/`, `scripts/`, `rules/`, `evaluation/golden_answers/`           |
| 3           | `mcp_server/src/mcp_server/semantic_index/`, `mcp_server/src/mcp_server/pipeline/semantic_search.py`     |
| 4           | `studio/`, `mcp_server/src/mcp_server/knowledge_graph/`                                                  |
| 5           | `studio/`, `rules/metrics/`, `dataset/dbt/models/metrics/`                                               |
| 6           | `mcp_server/src/mcp_server/pipeline/` (all steps), `mcp_server/src/mcp_server/app.py`                    |
| 7           | `mcp_server/src/mcp_server/resolvers/date_resolver.py`, `dataset/dbt/macros/date_format/`                |
| 8           | `mcp_server/src/mcp_server/pipeline/zone_router.py`, `dataset/dbt/models/*/gold/` vs `*/silver/`         |
| 9           | `mcp_server/src/mcp_server/resolvers/grain_resolver.py`                                                  |
| 10          | `mcp_server/src/mcp_server/business_rules/`, `rules/business_rules/`, `dataset/dbt/macros/business_rules/` |
| 11          | `evaluation/` (all subdirectories), `.github/workflows/`                                                 |
| 14          | Narrative only; no code in the companion repo.                                                           |

## Tables-to-chapter map

Seeded from `spec/generated/tables/`. Every spec table is assigned to the
chapter whose teaching arc depends on it. A chapter may also reference
tables assigned to earlier chapters; the primary assignment is the one
that *introduces* the table in the narrative.

### clinical_core (10 tables)

| Zone   | Table                         | First cited in |
| ------ | ----------------------------- | -------------- |
| bronze | `patient_bronze`              | Chapter 2      |
| silver | `patient`                     | Chapter 2      |
| silver | `encounter`                   | Chapter 2      |
| silver | `encounter_diagnosis`         | Chapter 7      |
| silver | `procedure`                   | Chapter 2      |
| silver | `observation`                 | Chapter 2      |
| silver | `lab_result`                  | Chapter 7      |
| silver | `medication_admin`            | Chapter 7      |
| gold   | `encounter_summary_monthly`   | Chapter 9      |
| gold   | `facility_month_kpi`          | Chapter 9      |

### revenue_cycle (7 tables)

| Zone   | Table                | First cited in |
| ------ | -------------------- | -------------- |
| silver | `claim_silver`       | Chapter 7      |
| silver | `claim_line_silver`  | Chapter 7      |
| gold   | `claim`              | Chapter 8      |
| gold   | `claim_line`         | Chapter 8      |
| gold   | `adjustment`         | Chapter 8      |
| gold   | `payment`            | Chapter 8      |
| gold   | `coverage`           | Chapter 8      |

### quality_reporting (4 tables)

| Zone | Table                         | First cited in |
| ---- | ----------------------------- | -------------- |
| gold | `quality_measure_enrollment`  | Chapter 10     |
| gold | `quality_event`               | Chapter 10     |
| gold | `readmission_index`           | Chapter 10     |
| gold | `exclusion_log`               | Chapter 10     |

### workforce (5 tables)

| Zone   | Table                          | First cited in |
| ------ | ------------------------------ | -------------- |
| silver | `provider`                     | Chapter 2      |
| silver | `provider_assignment`          | Chapter 9      |
| silver | `credential`                   | Chapter 2      |
| silver | `schedule`                     | Chapter 7      |
| gold   | `provider_productivity_month`  | Chapter 9      |

### supply_chain (6 tables)

| Zone   | Table                    | First cited in |
| ------ | ------------------------ | -------------- |
| bronze | `pharmacy_order_bronze`  | Chapter 7      |
| silver | `pharmacy_order`         | Chapter 7      |
| silver | `formulary`              | Chapter 10     |
| silver | `medical_supply_order`   | Chapter 2      |
| gold   | `formulary_current`      | Chapter 10     |
| gold   | `pharmacy_cost_month`    | Chapter 9      |

### reference (9 tables)

Reference data is used throughout; cited where it first appears.

| Zone | Table                     | First cited in |
| ---- | ------------------------- | -------------- |
| gold | `facility`                | Chapter 2      |
| gold | `calendar_fiscal`         | Chapter 9      |
| gold | `calendar_clinical`       | Chapter 9      |
| gold | `code_systems`            | Chapter 3      |
| gold | `terminology_registry`    | Chapter 3      |
| gold | `condition_to_category`   | Chapter 10     |
| gold | `business_rules_registry` | Chapter 10     |
| gold | `metrics_registry`        | Chapter 5      |
| gold | `kpi_snapshots`           | Chapter 11     |

## How to update this file

When a chapter draft changes which table it first cites, update the
corresponding row above. When a new table is added to the spec workbook,
re-run `make spec-export` to regenerate `spec/generated/`, then add a row
here so the map stays complete. This file is intentionally hand-edited
(not codegen'd) because the chapter assignment is an editorial decision
that only the author can make.
