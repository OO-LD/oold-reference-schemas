SHELL := /bin/sh

ZENSICAL := uvx --with pyyaml==6.0.2 zensical@0.0.46
PY := uv run --with pyld --with rdflib
VALIDATOR ?= .oold-schema
OOLD_VERSION ?= v1.0.0-rc.2

.PHONY: all generate mappings docs pages ontologies labels bump check validate serve clean release help

help:
	@echo "generate  regenerate everything derived from the schemas"
	@echo "bump      raise the versions the changes since the last release require"
	@echo "check     verify the tree is consistent with the schemas (what CI runs)"
	@echo "release   stamp a dated release and record which module versions it documents"
	@echo "ontologies fetch the pinned ontology snapshots and verify their hashes"
	@echo "validate  run the OO-LD validator over every module"
	@echo "serve     build and serve the documentation locally"

all: generate

# Order matters: the mapping sets are read by the schema pages, and the navigation is
# generated from what exists after both.
generate: mappings docs pages

mappings:
	python scripts/build_mappings.py

docs:
	$(PY) scripts/build_docs.py

pages:
	python scripts/build_pages.py

# Labels are fetched from the pinned ontologies and, for the few OBO terms no snapshot
# carries, from OLS. Deliberately not part of `generate`: refreshing them is tied to an
# ontology version bump, not to an ordinary edit.
ontologies:
	python scripts/fetch_ontologies.py

# One directory per pinned version, so a label records the pin it came from. Terms no
# snapshot covers are resolved from OLS.
ONTOLOGIES ?= $(wildcard .ontologies/*/*)

labels: ontologies
	uv run --with rdflib scripts/extract_labels.py $(ONTOLOGIES) --fetch-missing

# Computed from the last release rather than incremented, so running it twice is a no-op.
bump:
	python scripts/level.py --apply

# Mirrors the CI job. CI diffs a clean checkout; here the question is whether regenerating
# changes anything that was not already changed, so the target stays usable with work in
# progress. It deliberately does not seed pages, or a missing page would be created instead
# of reported.
check:
	@before=$$(git status --porcelain); \
	python scripts/build_mappings.py >/dev/null; \
	$(PY) scripts/build_docs.py >/dev/null; \
	test "$$before" = "$$(git status --porcelain)" || { \
		echo 'generated artefacts are stale: run make generate' >&2; exit 1; }
	python scripts/build_pages.py --check
	python scripts/level.py --check
	python scripts/release.py --check
	$(ZENSICAL) build --clean
	@# A macro that raises is swallowed by the renderer and published as text.
	@if grep -rnE '\{\{+ *(oold_|inline_file|example|vocabulary|render_schema|sssom_|mapping_|download)' site/; then 		echo "unrendered macro call in the built site" >&2; exit 1; 	fi

validate:
	@test -d $(VALIDATOR) || git clone --quiet --depth 1 --branch $(OOLD_VERSION) \
		https://github.com/OO-LD/oold-schema.git $(VALIDATOR)
	@npm ci --prefix $(VALIDATOR) --silent || npm install --prefix $(VALIDATOR) --silent
	@for dir in modules/*/; do \
		ls $$dir*.schema.json >/dev/null 2>&1 || continue; \
		node $(VALIDATOR)/scripts/validate.mjs $$dir || exit 1; \
		ls $$dir*.instance.json >/dev/null 2>&1 || continue; \
		uv run --with pyld scripts/effective_views.py $$dir || exit 1; \
	done

release:
	python scripts/check_identifiers.py --require
	python scripts/release.py
	$(MAKE) generate

serve: generate
	$(ZENSICAL) serve -a 127.0.0.1:8042

clean:
	rm -rf site docs/*/[0-9]*/ docs/mappings/*.sssom.tsv docs/mappings/crosswalks
