.DEFAULT_GOAL := start

API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 3000

.PHONY: help install ensure-env start dev backend frontend scrape index test test-backend test-frontend

help:
	@echo "make install   Install Python and Node dependencies, Chromium for scrape"
	@echo "make start     Create .env.local if needed, then start API and Next.js"
	@echo "make backend   Start FastAPI only"
	@echo "make frontend  Start Next.js only"
	@echo "make scrape    Download SANS policy PDFs into data/sans-policies/"
	@echo "make index     Embed Purpose/Scope summaries and extract safeguards"
	@echo "make test      Run the backend and frontend test suites"
	@echo "make test-backend   pytest only"
	@echo "make test-frontend  vitest only"

install:
	uv sync
	uv run playwright install chromium
	cd frontend && npm install

ensure-env:
	@if [ ! -f .env.local ]; then \
		cp .env.example .env.local; \
		echo "Created .env.local — paste AI_GATEWAY_API_KEY there."; \
	fi
	@if [ -f .env.example ]; then \
		while IFS= read -r line; do \
			key=$${line%%=*}; \
			case "$$key" in \
				""|\#*) continue ;; \
			esac; \
			if ! grep -q "^$${key}=" .env.local; then \
				printf '%s\n' "$$line" >> .env.local; \
				echo "Added $$key to .env.local."; \
			fi; \
		done < .env.example; \
	fi
	@if [ ! -f frontend/.env.local ]; then \
		cp frontend/.env.example frontend/.env.local; \
	fi

backend: ensure-env
	uv run uvicorn backend.main:app --reload --reload-dir backend --env-file .env.local --host $(API_HOST) --port $(API_PORT)

frontend: ensure-env
	cd frontend && npm run dev -- --port $(WEB_PORT)

start: ensure-env
	@echo "API  http://$(API_HOST):$(API_PORT)"
	@echo "Web  http://localhost:$(WEB_PORT)"
	@echo "Key  .env.local  (AI_GATEWAY_API_KEY)"
	@trap 'kill 0' EXIT INT TERM; \
		uv run uvicorn backend.main:app --reload --reload-dir backend --env-file .env.local --host $(API_HOST) --port $(API_PORT) & \
		cd frontend && npm run dev -- --port $(WEB_PORT)

dev: start

scrape: ensure-env
	uv run python -m backend.scraper

index: ensure-env
	uv run python -m backend.retrieve

# Both suites are offline: no API key, no network, no built index required.
test-backend:
	uv run pytest

test-frontend:
	cd frontend && npm test

# Runs both even if the first fails, then exits non-zero if either did, so one
# command shows every failure instead of stopping at the backend.
test:
	@fail=0; \
	echo "=== backend ==="; uv run pytest || fail=1; \
	echo "=== frontend ==="; (cd frontend && npm test --silent) || fail=1; \
	exit $$fail
