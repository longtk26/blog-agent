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

.PHONY: install run newmg mghead mgdown test test-unit
