PYTHON ?= python3
VENV := backend/.venv
VENV_BIN := $(VENV)/bin

.PHONY: setup dev dev-backend dev-frontend test lint format

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -e "backend[dev]"
	cd frontend && npm install

# Starts the API on :8000 and Vite on :5173; Ctrl+C stops both.
dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest

# Checks only; fails on any lint or formatting problem.
lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

# Applies the same tools' fixes.
format:
	cd backend && .venv/bin/ruff check --fix . && .venv/bin/ruff format .
	cd frontend && npm run format
