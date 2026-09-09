.DEFAULT_GOAL := start

API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 3000

.PHONY: help install ensure-env start dev backend frontend scrape index

help:
	@echo "make install   Install Python and Node dependencies, Chromium for scrape"
	@echo "make start     Create .env.local if needed, then start API and Next.js"
	@echo "make backend   Start FastAPI only"
	@echo "make frontend  Start Next.js only"
	@echo "make scrape    Download SANS policy PDFs into data/sans-policies/"
	@echo "make index     Embed Purpose/Scope summaries into the parked policy index"

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
