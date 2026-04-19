# Makefile for governed-ai-data-access
#
# This Makefile is the contract between the build phases described in
# docs/implementation_guide.md. Phase 2 (spec export and consistency)
# is fully wired. Later phases are stubbed with explicit NOT-YET-IMPLEMENTED
# messages so the target graph exists and Claude Code has a concrete skeleton
# to extend as the pipeline gets built.
#
# Run from the repo root. Environment variables (GCP_PROJECT, etc.) should be
# set via .envrc or your shell; they are never committed.

# ---- Configuration --------------------------------------------------------

PYTHON      ?= python
WORKBOOK    ?= spec/Companion_Dataset_Specification.xlsx
SPEC_OUT    ?= spec/generated

# GCP (override in .envrc; never commit credentials)
GCP_PROJECT          ?= companion-dev
GCP_LOCATION         ?= US
BQ_DATASET_STAGING   ?= staging_bronze
BQ_DATASET_COMPANION ?= companion_dev

# Synthea
SYNTHEA_JAR           ?= tools/synthea/synthea-with-dependencies.jar
SYNTHEA_PROPS         ?= dataset/config/synthea.properties
SYNTHEA_OUT           ?= tmp/synthea
SYNTHEA_SEED          ?= 42
SYNTHEA_POP_DEV       ?= 1000
SYNTHEA_POP_READER    ?= 10000
SYNTHEA_POP_CANONICAL ?= 100000

# Export for child processes (dbt, Python scripts)
export GCP_PROJECT GCP_LOCATION BQ_DATASET_STAGING BQ_DATASET_COMPANION


# ---- Help -----------------------------------------------------------------

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@echo ""
	@echo "  governed-ai-data-access: build targets"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "} \
		/^# ---- / {section=substr($$0,8); sub(/ -+$$/,"",section); printf "\n  \033[1m%s\033[0m\n", section} \
		/^[a-zA-Z_-]+:.*## / {printf "    \033[36m%-22s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)
	@echo ""


# ---- Environment ----------------------------------------------------------

.PHONY: venv
venv:  ## Create a .venv in the repo root
	$(PYTHON) -m venv .venv
	@echo "Run: source .venv/bin/activate"

.PHONY: install
install:  ## Install Python dependencies into the current venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e dataset/ingest
	$(PYTHON) -m pip install dbt-bigquery click pyyaml openpyxl pandas pyarrow jinja2 pytest ruff mypy

.PHONY: tools-check
tools-check:  ## Verify external tools (java, bq, dbt) are installed
	@command -v java  >/dev/null || { echo "java not found (needed for Synthea)"; exit 1; }
	@command -v bq    >/dev/null || { echo "bq not found (install the gcloud SDK)"; exit 1; }
	@command -v dbt   >/dev/null || { echo "dbt not found (pip install dbt-bigquery)"; exit 1; }
	@echo "All required tools present."


# ---- Phase 2: Spec export and consistency ---------------------------------

# File-based dependency: the stamp file in SPEC_OUT is newer than the workbook
# only when the export has run against the current workbook. This means
# `make spec-check` automatically re-exports when the workbook changes.

$(SPEC_OUT)/.timestamp: $(WORKBOOK) scripts/export_spec_to_yaml.py
	$(PYTHON) scripts/export_spec_to_yaml.py --workbook $(WORKBOOK) --out $(SPEC_OUT)
	@touch $(SPEC_OUT)/.timestamp

.PHONY: spec-export
spec-export: $(SPEC_OUT)/.timestamp  ## Export workbook to spec/generated/*.yaml

.PHONY: spec-check
spec-check: spec-export  ## Verify cross-references in spec/generated
	$(PYTHON) scripts/spec_consistency_check.py --spec-dir $(SPEC_OUT)

.PHONY: spec-check-strict
spec-check-strict: spec-export  ## Strict check (warnings fail; use in CI)
	$(PYTHON) scripts/spec_consistency_check.py --spec-dir $(SPEC_OUT) --strict

.PHONY: spec
spec: spec-check  ## Alias for spec-export + spec-check


# ---- Phase 3: Synthea generation ------------------------------------------

.PHONY: synthea-dev
synthea-dev:  ## Run Synthea at dev scale (1,000 patients, ~3 min)
	@mkdir -p $(SYNTHEA_OUT)/dev
	java -jar $(SYNTHEA_JAR) \
		-c $(SYNTHEA_PROPS) \
		-s $(SYNTHEA_SEED) \
		-p $(SYNTHEA_POP_DEV) \
		--exporter.baseDirectory $(SYNTHEA_OUT)/dev

.PHONY: synthea-reader
synthea-reader:  ## Run Synthea at reader scale (10,000 patients, ~15 min)
	@mkdir -p $(SYNTHEA_OUT)/reader
	java -jar $(SYNTHEA_JAR) \
		-c $(SYNTHEA_PROPS) \
		-s $(SYNTHEA_SEED) \
		-p $(SYNTHEA_POP_READER) \
		--exporter.baseDirectory $(SYNTHEA_OUT)/reader

.PHONY: synthea-canonical
synthea-canonical:  ## Run Synthea at canonical scale (100,000 patients, ~30 min)
	@mkdir -p $(SYNTHEA_OUT)/canonical
	java -jar $(SYNTHEA_JAR) \
		-c $(SYNTHEA_PROPS) \
		-s $(SYNTHEA_SEED) \
		-p $(SYNTHEA_POP_CANONICAL) \
		--exporter.baseDirectory $(SYNTHEA_OUT)/canonical


# ---- Phase 4-6: Ingest (stubs) --------------------------------------------

.PHONY: project
project:  ## [STUB] Project Synthea FHIR to staging_bronze (Phase 4)
	@echo "Not yet implemented. See Phase 4 of docs/implementation_guide.md."; exit 1

.PHONY: inject
inject:  ## [STUB] Format injection (Phase 5)
	@echo "Not yet implemented. See Phase 5 of docs/implementation_guide.md."; exit 1

.PHONY: synthetic
synthetic:  ## [STUB] Generate synthetic tables (Phase 6)
	@echo "Not yet implemented. See Phase 6 of docs/implementation_guide.md."; exit 1

.PHONY: ingest
ingest: project inject synthetic  ## Full ingest pipeline (Phases 4-6)


# ---- Phase 8: Codegen (stubs) ---------------------------------------------

.PHONY: codegen-rules
codegen-rules: spec-check  ## [STUB] Generate dbt macros from rules YAML (Phase 8)
	@echo "Not yet implemented. See Phase 8 of docs/implementation_guide.md."; exit 1

.PHONY: codegen-kpis
codegen-kpis: spec-check  ## [STUB] Generate KPI dbt models from kpi YAML (Phase 8)
	@echo "Not yet implemented. See Phase 8 of docs/implementation_guide.md."; exit 1

.PHONY: codegen
codegen: codegen-rules codegen-kpis  ## Run all codegen


# ---- Phase 9-11: dbt ------------------------------------------------------

.PHONY: dbt-deps
dbt-deps:  ## Install dbt packages
	cd dataset/dbt && dbt deps

.PHONY: dbt-seed
dbt-seed:  ## Load seed CSVs into BigQuery
	cd dataset/dbt && dbt seed

.PHONY: dbt-build
dbt-build: codegen  ## Build all dbt models
	cd dataset/dbt && dbt build

.PHONY: dbt-test
dbt-test:  ## Run dbt tests only
	cd dataset/dbt && dbt test


# ---- Phase 12: Evaluation harness (stub) ----------------------------------

.PHONY: eval
eval:  ## [STUB] Run the evaluation harness (Phase 12)
	@echo "Not yet implemented. See Phase 12 of docs/implementation_guide.md."; exit 1


# ---- End-to-end bootstraps ------------------------------------------------

.PHONY: bootstrap-dev
bootstrap-dev: spec-check synthea-dev ingest dbt-build eval  ## Full dev build (runs locally, ~10 min once all phases exist)

.PHONY: bootstrap-reader
bootstrap-reader: spec-check synthea-reader ingest dbt-build eval  ## Full reader-scale build (~30 min, ~$2)

.PHONY: bootstrap-canonical
bootstrap-canonical: spec-check synthea-canonical ingest dbt-build eval  ## Full canonical build (~3 hrs, ~$25)


# ---- CI --------------------------------------------------------------------

.PHONY: ci
ci: spec-check-strict  ## Local simulation of what CI runs on every commit
	@echo ""
	@echo "CI would also run: bootstrap-dev + eval (once phases are wired)"


# ---- Cleanup --------------------------------------------------------------

.PHONY: clean-spec
clean-spec:  ## Remove generated spec YAML
	rm -rf $(SPEC_OUT)

.PHONY: clean-synthea
clean-synthea:  ## Remove Synthea output
	rm -rf $(SYNTHEA_OUT)

.PHONY: clean-dbt
clean-dbt:  ## Remove dbt target/ and dbt_packages/
	rm -rf dataset/dbt/target dataset/dbt/dbt_packages dataset/dbt/logs

.PHONY: clean
clean: clean-spec clean-dbt  ## Remove generated artifacts (preserves Synthea output)

.PHONY: clean-all
clean-all: clean clean-synthea  ## Remove everything including Synthea output
