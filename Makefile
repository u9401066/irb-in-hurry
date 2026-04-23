.PHONY: help setup generate pdf preview dashboard checklist report-kmuh review clean test all new kmuh-seq closure amendment continuing

define SET_PHASE
	$(RUN) python -c "import yaml; c=yaml.safe_load(open('$(CONFIG)')); c['phase']='$(1)'; c.setdefault('harness',{}); c['harness']['group_by_phase']=True; c['harness']['phases']=['$(1)']; yaml.dump(c,open('$(CONFIG)','w'),allow_unicode=True,default_flow_style=False,sort_keys=False)"
endef

define SET_PHASE_SEQUENCE
	$(RUN) python -c "import yaml; c=yaml.safe_load(open('$(CONFIG)')); c['phase']='$(1)'; c.setdefault('harness',{}); c['harness']['group_by_phase']=True; c['harness']['phases']=['new','amendment','continuing','closure']; yaml.dump(c,open('$(CONFIG)','w'),allow_unicode=True,default_flow_style=False,sort_keys=False)"
endef

CONFIG := config.yml
OUTPUT := output
RUN := uv run

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies
	uv sync

generate: ## Generate DOCX forms from config.yml
	$(RUN) python scripts/generate_all.py $(CONFIG)

pdf: ## Convert DOCX → PDF + PNG previews
	$(RUN) python scripts/convert.py $(OUTPUT)

all: generate pdf dashboard ## Generate + convert + dashboard

dashboard: ## Show submission status
	./dashboard.sh $(CONFIG)

report-kmuh: ## Show KMUH phase-by-phase generation diff report
	$(RUN) python scripts/report_kmuh.py $(CONFIG)

checklist: ## View checklist
	@for f in $$(find output -type f -name "checklist.md" | sort); do \
		echo "===== $$f ====="; \
		cat "$$f"; \
		echo; \
		done

review: ## Run simulated IRB reviewer on generated forms
	$(RUN) python scripts/reviewer.py $(CONFIG)

test: ## Run tests
	$(RUN) pytest tests/ -v

clean: ## Remove generated files
	find $(OUTPUT) -type f \( -name "*.docx" -o -name "*.pdf" -o -name "*.png" \) -delete 2>/dev/null; true
	find $(OUTPUT) -type d -name preview -empty -delete 2>/dev/null; true

new: ## Set phase to new case + generate
	$(call SET_PHASE,new)
	$(MAKE) all

kmuh-seq: ## Set KMUH full pipeline sequence and generate
	$(call SET_PHASE_SEQUENCE,new)
	$(MAKE) all

closure: ## Set phase to closure + generate
	$(call SET_PHASE,closure)
	$(MAKE) all

amendment: ## Set phase to amendment + generate
	$(call SET_PHASE,amendment)
	$(MAKE) all

continuing: ## Set phase to continuing review + generate
	$(call SET_PHASE,continuing)
	$(MAKE) all
