.PHONY: install test coverage run lint

PY := .venv/bin/python

install:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest

coverage:
	$(PY) -m pytest --cov=src/application --cov=src/infrastructure --cov-report=term-missing --cov-fail-under=60

run:
	$(PY) -m src.interface.bot

lint:
	$(PY) -m ruff check src tests
