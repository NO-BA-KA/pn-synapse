
PY=python3
VENV=.venv
PIP=$(VENV)/bin/pip
PYBIN=$(VENV)/bin/python
RUFF=$(VENV)/bin/ruff
PYTEST=$(VENV)/bin/pytest

.PHONY: setup dev test lint format clean

setup:
    @if [ ! -d $(VENV) ]; then $(PY) -m venv $(VENV); fi
    $(PIP) install -U pip
    $(PIP) install -r requirements.txt

dev:
    $(VENV)/bin/uvicorn synapse_app:app --reload --port 8000

test:
    $(PYTEST) -q

lint:
    $(RUFF) check .

format:
    $(RUFF) format .

clean:
    rm -rf $(VENV) .pytest_cache __pycache__
