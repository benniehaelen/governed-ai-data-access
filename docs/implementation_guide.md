# Companion repo implementation guide

A phased, executable plan for building the dataset portion of the `governed-ai-data-access` monorepo, using Claude Code where it pays off and authoring by hand where correctness matters most. By the end of Phase 13, the dataset is sitting in BigQuery with golden answers pinned and the evaluation harness green, which is exactly what Chapter 3 needs as its starting point.

Estimated total calendar time at half-time: 8 to 10 weeks if Claude Code handles the scaffolding and ingest phases under review. Less if full-time.

## Conventions used in this guide

Each phase has five parts:

1. **Goal**. What this phase produces.
2. **Inputs**. What must already exist before starting.
3. **Work**. The concrete steps.
4. **Claude Code prompt**. A template prompt when Claude Code is the right tool. Omitted when the phase is better done by hand.
5. **Checkpoint**. A verifiable test that must pass before moving on.

"Review" means read the output line by line and push back where it is wrong. "Accept" means run the tests and move on. The phases marked **Review-critical** are the ones where skipping review will cost you weeks later.

---

## Phase 0. Prerequisites

**Goal.** Tools installed, GCP project configured, Claude Code authenticated.

**Work.**

1. Create a dedicated GCP project for the companion data. Name it something like `governed-ai-companion-dev`. Enable the BigQuery, Vertex AI, Cloud Storage, and IAM APIs.
2. Create two BigQuery datasets in that project: `staging_bronze` and `companion_dev`. Set default table expiration to none.
3. Create a service account with `bigquery.admin` on the project. Download the key to `~/.gcp/companion_dev_sa.json`. Do not commit.
4. Install locally: Python 3.11+, Node.js 20+ (needed later for Studio), dbt-bigquery 1.8+, Java 17+ (Synthea requirement), the gcloud CLI, and Claude Code.
5. `gcloud auth application-default login` and confirm `bq ls` against the project works.
6. Set environment variables in a `.envrc` or equivalent: `GCP_PROJECT`, `BQ_LOCATION` (US recommended), `GOOGLE_APPLICATION_CREDENTIALS`.

**Checkpoint.** `bq query --use_legacy_sql=false 'SELECT 1'` returns 1.

---

## Phase 1. Scaffold the monorepo

**Goal.** The empty monorepo structure from Section 4 of the pipeline plan exists on disk, with placeholder configs.

**Inputs.** The pipeline plan, the spec workbook.

**Work.** Let Claude Code do this.

**Claude Code prompt.**

> Read `docs/pipeline_plan.docx` and `spec/Companion_Dataset_Specification.xlsx`. Create the monorepo directory structure from Section 4 of the pipeline plan. Produce:
>
> 1. Top-level `README.md`, `Makefile`, `.gitignore`, `.python-version`, `.tool-versions`.
> 2. `dataset/ingest/pyproject.toml` with dependencies: google-cloud-bigquery, google-cloud-storage, pandas, pyarrow, pydantic, click, pyyaml, jinja2, pytest, ruff, mypy. Pin minor versions.
> 3. `dataset/dbt/dbt_project.yml`, `dataset/dbt/profiles.yml.template`, empty model folders matching the six Data Products from the workbook's Data Products sheet.
> 4. `rules/business_rules/` and `rules/metrics/` directories with READMEs explaining the YAML shape.
> 5. `evaluation/` skeleton with subdirectories matching Section 4.5.
> 6. `scripts/spec_consistency_check.py` skeleton that reads the workbook and lists tables, rules, and KPIs. No consistency logic yet; just load and print.
> 7. `docs/chapter_map.md` seeded from the table sheet.
>
> Do not generate any SQL or Python business logic yet. This is scaffolding only.

**Checkpoint.** `tree -L 3` matches the Section 4 layout. `python scripts/spec_consistency_check.py` prints 41 tables, 20 rules, 19 KPIs.

---

## Phase 2. Encode the spec as YAML

**Goal.** The workbook's Tables, Business Rules, KPIs, and Data Products sheets are mirrored as version-controlled YAML under `spec/generated/`, so downstream phases never parse Excel directly.

**Inputs.** The workbook.

**Work.** Run a one-time export script. Claude Code can write this.

**Claude Code prompt.**

> Write `scripts/export_spec_to_yaml.py` that reads `spec/Companion_Dataset_Specification.xlsx` and produces:
>
> - `spec/generated/tables/<data_product>/<table>.yaml` with all columns from the Tables sheet for that row.
> - `spec/generated/business_rules/<RULE_CODE>.yaml` per row in Business Rules.
> - `spec/generated/kpis/<METRIC_CODE>.yaml` per row in KPIs.
> - `spec/generated/data_products.yaml` from Data Products.
> - `spec/generated/date_format_coverage.yaml` from that sheet.
>
> Preserve every column. Use snake_case keys. Headers are on row 4 of each sheet (0-indexed row 3). Include a `_source_row` field pointing back to the Excel row for traceability.

**Checkpoint.** 41 table YAMLs, 20 rule YAMLs, 19 KPI YAMLs. `spec_consistency_check.py` now reads the YAML rather than Excel and still reports the same counts.

This phase matters because it ends the dependency on Excel parsing for every downstream step. The workbook remains the source of truth; the YAML is the build artifact the code consumes. If someone updates the workbook, re-running this script is the one place that sees Excel.

---

## Phase 3. Generate Synthea population (Stage 1)

**Goal.** FHIR bundles for 1,000 patients (dev scale) sitting in `tmp/synthea/`.

**Inputs.** None beyond Phase 0.

**Work.** No Claude Code needed. This is a single `java -jar` invocation.

1. Download Synthea master JAR to `tools/synthea/`. Pin the version: record the exact tag in `dataset/config/synthea.properties` and in the repo README.
2. Write `dataset/config/synthea.properties` with seed fixed (use `42` for dev), population `1000`, FHIR R4 output, and state distribution matching your target (I recommend one state for determinism; the Synthea state distribution is itself a source of variance).
3. `make synthea-dev` invokes the JAR.
4. Verify output: bundle counts, FHIR resource diversity.

**Checkpoint.** `find tmp/synthea -name '*.json' | wc -l` is between 1,000 and 1,100 (allows for hospitals and practitioner bundles). Pick one bundle at random and confirm it has the expected FHIR resources.

---

## Phase 4. Project FHIR to staging_bronze (Stage 2)

**Goal.** Staging tables in BigQuery, one per FHIR resource type, populated from the bundles.

**Inputs.** Synthea output, Phase 2 YAML (for target schemas).

**Work.** **Review-critical.** Claude Code can write the modules but you review each one against the FHIR spec. Bugs here propagate everywhere.

**Claude Code prompt.**

> For each FHIR resource in this list, write a projection module under `dataset/ingest/src/ingest/fhir_to_staging/<resource>.py`: Patient, Encounter, Condition, Procedure, Observation, MedicationAdministration, Practitioner, Claim, ExplanationOfBenefit, CareTeam.
>
> Each module exposes `project(bundles_dir: Path, bq_client) -> None` that reads bundles, extracts the resource, flattens to a row, and writes to `staging_bronze.<resource_lowercase>` in BigQuery using pyarrow and the BigQuery storage write API.
>
> Target schemas for the subset of columns we carry downstream are in `spec/generated/tables/clinical_core/*.yaml`. Map FHIR fields to those columns. For fields not in the target schema, drop them. For fields in the target schema not in FHIR, emit NULL.
>
> Include a `tests/projection/` test per module that runs against a three-patient fixture bundle and asserts row count and primary-key uniqueness.

After Claude Code produces the modules:

1. Run the fixture tests. Any failures mean the mapping is wrong.
2. Read each module and verify the FHIR path extractions against `https://hl7.org/fhir/R4/`. Common traps: `Encounter.period.start` vs `Encounter.period.end`, `CodeableConcept.coding[0].code` vs `CodeableConcept.text`, `Reference.reference` parsing.
3. Run `make project-dev`. Verify staging_bronze tables appear in BigQuery with expected row counts (patient_bronze should have 1,000 rows at dev scale, encounter should have roughly 20,000 to 40,000).

**Checkpoint.** All ten staging tables present. Fixture tests green. Row counts reasonable.

---

## Phase 5. Format injection (Stage 3)

**Goal.** The date-format heterogeneity the DateResolver exists to address, manufactured deterministically.

**Inputs.** staging_bronze populated.

**Work.** Straight Python; Claude Code can write this cleanly.

**Claude Code prompt.**

> Write `dataset/ingest/src/ingest/format_injection/inject.py` that implements the five conversions listed in Section 3 Stage 3 of the pipeline plan:
>
> 1. lab_result.result_ts (TIMESTAMP) -> result_epoch_s (INT64 seconds)
> 2. medication_admin.admin_time (TIMESTAMP) -> admin_time_str (STRING %Y-%m-%d %H:%M:%S)
> 3. claim_silver.service_date (DATE) -> service_date_str (STRING %m/%d/%Y)
> 4. schedule.shift_start (TIMESTAMP) -> shift_start_epoch_ms (INT64 milliseconds)
> 5. pharmacy_order_bronze.order_time (TIMESTAMP) -> order_time_epoch_ms (INT64 milliseconds)
>
> For each: read the staging_bronze table, add the injected column, write back. Preserve the original column in an `staging_bronze_archive` dataset for reversibility.
>
> Implement as BigQuery SQL statements (ALTER TABLE ADD COLUMN, UPDATE) rather than Python round-trips. Generate the SQL from the target schema YAML so the injection stays in sync with the spec.
>
> Add an integration test that asserts, for a handful of randomly sampled rows, that parsing the injected column back yields the original timestamp.

**Checkpoint.** Every date-storage variant in the workbook's Date Format Coverage sheet has at least one populated column in staging_bronze. The roundtrip test passes for all five conversions.

---

## Phase 6. Generate synthetic tables (Stage 4)

**Goal.** Tables Synthea does not produce (`provider_assignment`, `credential`, `schedule`, `adjustment`, `payment`, `coverage`, `formulary`, `medical_supply_order`, `pharmacy_order_bronze`) populated with deterministic synthetic data at dev scale.

**Inputs.** Phase 4 staging_bronze (for joins back to patient and encounter).

**Work.** **Review-critical and specification-critical.** This is the phase where the workbook is incomplete and Claude Code will invent if you let it. You need to author a distribution spec first.

1. Write `docs/synthetic_distributions.md` specifying for each synthetic table: row-count target at dev/reader/canonical scale, cardinality per upstream entity (e.g., "each patient has 1.0 to 1.3 coverage periods, right-skewed"), amount distributions with mean and variance (e.g., "adjustment amounts are log-normal with mu=5.2, sigma=1.1"), temporal patterns (e.g., "schedule shifts cluster on weekdays 7am-7pm and 7pm-7am").
2. This document is yours to author. Do not ask Claude Code to invent distributions. A half-day of careful spec here saves weeks of "why do my KPIs not match the book" debugging later.
3. Once the spec exists, Claude Code can implement the generators.

**Claude Code prompt (after distributions are specified).**

> For each synthetic table listed in `docs/synthetic_distributions.md`, write a generator under `dataset/ingest/src/ingest/synthetic/<table>.py` that produces the table to match the specified distributions.
>
> Derive each generator's seed from the global seed by hashing the module name (use hashlib.md5(name) and take the first 4 bytes as an int). This guarantees module independence.
>
> Implement each as a pandas DataFrame, then write via the BigQuery client. Include a test that asserts row count is within 1% of target and that distributional assertions from the spec hold within tolerance.

**Checkpoint.** Every synthetic table populated. Distribution tests green. Spot-check one or two tables by hand against the spec doc.

---

## Phase 7. dbt project configuration

**Goal.** dbt is configured against the dev profile and can compile (but not yet build, since there are no models).

**Inputs.** Phase 6 complete.

**Work.** Short Claude Code ask. Review the profiles.yml.template and ensure no secrets leak into the repo.

**Claude Code prompt.**

> Flesh out `dataset/dbt/dbt_project.yml`:
>
> - name: companion
> - model-paths, seed-paths, macro-paths, test-paths standard layout
> - For each of the six Data Products, declare `materialized: table` by default with partitioning and clustering hints (see spec/generated/tables for partition columns)
> - seeds configured to load the reference CSVs with explicit column types
>
> Write `dataset/dbt/profiles.yml.template` (not profiles.yml) with the bigquery profile, using env vars for project, dataset, service-account path, and location.
>
> Run `dbt compile` and resolve any errors so the empty project compiles cleanly.

**Checkpoint.** `dbt compile` and `dbt debug` both succeed against the dev profile.

---

## Phase 8. Rules codegen (transforms workbook rules into dbt macros)

**Goal.** The 20 business rules from the workbook, rendered as dbt macros, driven by a codegen script that keeps the YAML as source of truth.

**Inputs.** Phase 2 YAML rules. The SQL fragments are already present in the workbook.

**Work.** **Review-critical for the generator, accept for the macros.**

**Claude Code prompt.**

> Write `scripts/codegen_rules.py` that:
>
> 1. Walks `rules/business_rules/*.yaml`
> 2. For each rule, generates a dbt macro at `dataset/dbt/macros/business_rules/<rule_code_lowercase>.sql` using a Jinja template
> 3. The macro takes a table reference and returns the SQL WHERE fragment from the rule's `sql_fragment` field, wrapped in a macro with arguments that match the rule's `applies_to` columns
> 4. Includes a header comment in each generated macro pointing to the source YAML and the workbook source row
> 5. Is idempotent: re-running produces identical files
>
> Also write `scripts/codegen_kpis.py` that walks `rules/metrics/*.yaml` and generates a dbt model per KPI at `dataset/dbt/models/metrics/<metric_code_lowercase>.sql`, using the `canonical_formula` field.
>
> Hook both into the Makefile as `make codegen`.

Review steps:

1. Read `codegen_rules.py` end to end. Verify it handles the edge cases in the workbook: rules whose SQL fragment references multiple columns, rules with multi-line SQL, rules where the `applies_to` column has multiple entries.
2. Run `make codegen`. Spot-check five generated macros against the workbook SQL fragments. They must match exactly.
3. Commit both the generator and the generated macros (the generated macros are build artifacts but committing them makes code review and diffs easier).

**Checkpoint.** 20 macros under `dataset/dbt/macros/business_rules/`. 5 models under `dataset/dbt/models/metrics/`. `dbt parse` succeeds.

---

## Phase 9. Bronze and silver models (Stages 5-6)

**Goal.** The bronze passthroughs and silver cleansed tables materialize from staging_bronze.

**Inputs.** Phase 8 macros, Phase 2 table YAML.

**Work.** **Review-critical.** This is where enterprise semantics get encoded. Claude Code writes the boilerplate; you review the logic.

**Claude Code prompt, one Data Product at a time.**

> Generate dbt models for the clinical_core Data Product based on `spec/generated/tables/clinical_core/*.yaml`. For each table:
>
> - Bronze models: thin wrapper selecting from `staging_bronze.<source_table>` with the columns declared in the YAML.
> - Silver models: apply the recency pattern from the YAML (e.g., `timestamp_rank` for patient). Apply the business rules listed in the table YAML's `business_rules` column using the macros from Phase 8. For LOS calculation, apply `RULE_LOS_WHOLE_DAYS` from the workbook.
> - Each model includes a `schema.yml` entry with unique tests on the PK column(s), not_null on the PK, and accepted_values on any enum columns declared in the YAML.
> - Partition and cluster each table per the YAML's date column and any clustering hints.
>
> Do NOT generate models for gold, metrics, or quality_reporting yet. Only clinical_core bronze and silver.

Review steps per Data Product:

1. Read every silver model. Verify the dedup logic matches the workbook's recency pattern.
2. For tables with business rules applied, verify the macro call is correct and the rule fires at the right grain.
3. Run `dbt run --select clinical_core.silver` against dev. Verify row counts roughly match the workbook's expected counts, scaled down from 100k patients to 1k (divide by 100).

Repeat the prompt for `revenue_cycle`, `workforce`, `supply_chain`. Leave `quality_reporting` for Phase 10 because its governance model differs.

**Checkpoint.** All silver tables materialize. `dbt test --select silver` passes. Row counts within 20% of scaled expectations.

---

## Phase 10. Gold models and quality_reporting (Stages 7-8)

**Goal.** Gold marts and the quality_reporting Data Product materialize correctly, with CMS exclusions applied.

**Inputs.** Phase 9 silver complete.

**Work.** **Review-critical.** Gold is where governance teaching happens.

**Claude Code prompt.**

> Generate gold models for the four Data Products that have gold zones (clinical_core, revenue_cycle, workforce, supply_chain), based on the YAML specs and the pipeline plan Section 3 Stage 7.
>
> For each gold table, apply the rules listed in its YAML. Key rules to verify are applied:
>
> - clinical_core.encounter_summary_monthly: aggregates silver.encounter by patient/month/facility.
> - revenue_cycle.claim: applies RULE_CLAIM_DENIED_EXCLUDE and RULE_LATE_PAYMENT_ADJUSTMENT.
> - supply_chain.formulary_current: applies RULE_FORMULARY_CURRENT_ONLY.
>
> Then generate quality_reporting models. This Data Product is gold-only, reads directly from clinical_core.silver and revenue_cycle.gold, and applies the CMS rules: RULE_CMS_AMI_EXCLUSIONS, RULE_CMS_CHF_EXCLUSIONS, RULE_PLANNED_READMIT_EXCLUDE, RULE_DECEASED_INDEX_EXCLUDE.
>
> Include schema.yml tests for each gold table.

Review steps:

1. For each gold model, trace the rule applications against the workbook. The silver-to-gold numerical differences are the book's Chapter 8 teaching material; if they are wrong here, Chapter 8 has nothing to stand on.
2. Pay special attention to `readmission_index`. This table drives the AMI readmission KPI and has multiple rules composed.
3. Run the full dbt build and diff silver versus gold counts for `claim` and `claim_line`. The delta is the rule-application delta and should make sense.

**Checkpoint.** `dbt build --select gold` passes. Silver-vs-gold deltas on claims are non-trivial and traceable to specific rules.

---

## Phase 11. Metrics and KPI snapshots (Stage 9)

**Goal.** `kpi_snapshots` is populated with the five KPIs. At dev scale, values are directional; at canonical scale, they match the workbook's known-good answers.

**Inputs.** Phase 10 gold complete. The 5 KPI YAMLs from Phase 2.

**Work.** **Author-critical, not Claude-Code-critical.** The canonical formulas are in the workbook, but Claude Code's previous output should be reviewed very carefully here because the KPIs are what the book is measured against.

1. Open each metric YAML under `rules/metrics/*.yaml`. Verify the `canonical_formula` field matches the workbook's Canonical Formula column exactly.
2. Run `make codegen` to regenerate the metric dbt models. Review each generated SQL.
3. Add the "plausibly wrong" implementations from the workbook's KPI sheet as commented-out alternatives in each model, with a comment explaining why they are wrong. This is teaching material Chapter 11 uses.
4. Run `dbt run --select metrics`. Inspect `kpi_snapshots`.

**Checkpoint.** At dev scale, all five KPIs produce values in plausible ranges. You cannot check known-good answers yet because those are at canonical scale.

---

## Phase 12. Evaluation harness (Stage 10)

**Goal.** The test suite that Chapter 11 will formalize is in place and wired to CI.

**Inputs.** All prior phases.

**Work.** Mostly Claude Code, with a hand-authored review.

**Claude Code prompt.**

> Build the evaluation harness under `evaluation/`:
>
> 1. `evaluation/retrieval_tests/` scaffolding only (the actual retrieval tests come later with the MCP Server).
> 2. `evaluation/resolver_tests/` skeleton with placeholder tests for DateResolver, RecencyResolver, GrainResolver. Each test reads a metadata fixture from spec/generated/ and asserts resolver output. The resolvers themselves don't exist yet; use stubs that will be replaced when the MCP Server is built.
> 3. `evaluation/sql_validation/` with a dbt_build_succeeds test and a schema_tests_pass test.
> 4. `evaluation/regression_harness/compare_kpi_snapshots.py` that loads `evaluation/golden_answers/kpi_snapshots.csv` and compares to current `kpi_snapshots` with configurable tolerance (default 1%).
> 5. A top-level `evaluation/run_all.py` that invokes all harness components and exits non-zero on any failure.
>
> Wire into CI: `.github/workflows/ci.yml` runs `make synthea-dev`, `make ingest`, `dbt build`, `python evaluation/run_all.py` on every commit.

**Checkpoint.** `python evaluation/run_all.py` succeeds at dev scale. CI green on a fresh clone.

---

## Phase 13. Canonical run and golden answers

**Goal.** The 100,000-patient canonical dataset exists in BigQuery, and `evaluation/golden_answers/kpi_snapshots.csv` holds the known-good KPI values that the book will reference.

**Inputs.** Everything above, working at dev scale.

**Work.** This is the expensive run. Do not skip steps.

1. Scale config: set `dataset.yaml` to canonical (100,000 patients).
2. `make synthea-canonical`. This takes around 30 minutes.
3. `make ingest-canonical`. Takes 30 to 45 minutes; most time is BigQuery loads.
4. `make dbt-build-canonical`. Takes 45 to 60 minutes; watch costs.
5. Query `kpi_snapshots` in BigQuery. Compare to the workbook's "Known-Good Answer" column in the KPIs sheet. Values should match within 1%.
6. If values do NOT match: you have a bug. Stop. Do not proceed. Diff the gold tables against expected row counts; usually the discrepancy traces to a rule that is not firing or firing at the wrong grain. The workbook's "Plausibly wrong" column is your hint sheet.
7. Once values match, export `kpi_snapshots` to `evaluation/golden_answers/kpi_snapshots.csv` and commit. These are the numbers the book cites. From this moment on, any change that moves them is a release event.

**Checkpoint.** `METRIC_AMI_READMIT_30D` matches "8.2% at 2024 Q3". `METRIC_LOS_AVG` matches "4.7 days at 2024 Q3". `METRIC_ED_DOOR_TO_PROVIDER` matches "4 minutes median at 2024 Q3". And so on for the remaining two.

---

## Phase 14. Tag chapter-02 and hand off

**Goal.** The repository is at a known-good state, tagged, and ready for Chapter 3 to start building the retrieval layer against.

**Work.**

1. Tag: `git tag -a chapter-02 -m "Dataset pipeline complete, golden answers pinned"`.
2. Update `docs/chapter_map.md` with the chapter-02 state: what exists, what does not, which subsystems (spec, rules, dataset) are in use and which (mcp_server, studio) are stubs.
3. Draft the Chapter 3 preconditions doc: what a reader cloning at `chapter-02` sees, what they run, what questions they can ask the dataset (via raw BigQuery SQL; the MCP Server comes in Chapter 3).

**Checkpoint.** A fresh clone plus `make bootstrap-canonical` reproduces the canonical dataset from scratch in under three hours.

---

## How to use Claude Code across this plan

Three patterns worth internalizing:

1. **Prompt with the spec attached.** Every Claude Code prompt above assumes Claude Code has read access to `docs/pipeline_plan.docx`, `spec/Companion_Dataset_Specification.xlsx`, and the prior phases' YAML outputs. Start every session by confirming that, and reference specific workbook cells or rows in prompts. "The rule from row 5 of the Business Rules sheet" is more reliable than "the LOS rule".

2. **One Data Product at a time.** When you get to Phase 9 and Phase 10, do not ask Claude Code to generate all six Data Products at once. Do one, review, test, commit, move on. The review step only works if the diff is small.

3. **Flag and defer.** If Claude Code produces SQL that looks right but you are not sure, leave a `-- REVIEW: <reason>` comment in the generated file and keep going. Come back to the list before Phase 13. Do not proceed past Phase 11 with unreviewed `-- REVIEW` comments in gold or metrics models.

## Things Claude Code will want to do that you should decline

- Rewriting the workbook's SQL fragments to be "cleaner" or "more idiomatic". The workbook is the contract. Codegen preserves it exactly.
- Generating synthetic distributions without a spec. Phase 6's `synthetic_distributions.md` exists precisely to prevent this.
- Making the evaluation harness "smarter" by allowing KPI values to float within wider tolerances. 1% is not an accident; it is calibrated against APPROX_QUANTILES drift.
- Adding "helpful" features to the dbt project (incremental materializations, snapshot tables, extra tests). Keep the surface area minimal until Chapter 3.

## What you own, start to finish

- The Phase 6 distribution spec. No one else can write this.
- The Phase 11 KPI review. The book's numbers are only as good as this review.
- The Phase 13 canonical run interpretation. When a KPI does not match, you are the one who diagnoses it.

Everything else is fair game for Claude Code under review.
