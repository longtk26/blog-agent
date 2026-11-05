PY ?= .venv/bin/python

install:
	uv venv -q .venv --python 3.12 || python3 -m venv .venv
	uv pip install --python $(PY) -r requirements-dev.txt || $(PY) -m pip install -r requirements-dev.txt
run:
	$(PY) -m fastapi dev src/main.py --host 127.0.0.1 --port 8100
newmg:
	$(PY) -m alembic revision --autogenerate -m "$(name)"
mghead:
	$(PY) -m alembic upgrade head
mgdown:
	$(PY) -m alembic downgrade -1
test:
	$(PY) -m pytest -q
test-unit:
	$(PY) -m pytest -q -m "not integration"
diagrams-icons: ## Rebuild the icon catalogue + shape-name fixture from the pinned draw.io index (E10-S3/S4)
	$(PY) -m src.modules.diagrams.scripts.build_icon_catalogue $(if $(REFRESH),--refresh)
diagrams-shape-index: diagrams-icons
eval-sync:
	uv run python src/modules/evaluation/scripts/sync_dataset.py
eval:
	uv run python src/modules/evaluation/scripts/run_eval.py $(if $(EXPERIMENT),--experiment "$(EXPERIMENT)")
eval-compare:
	uv run python src/modules/evaluation/scripts/compare_experiments.py --base "$(BASE)" --new "$(NEW)"

.PHONY: install run newmg mghead mgdown test test-unit diagrams-icons diagrams-shape-index eval-sync eval eval-compare
