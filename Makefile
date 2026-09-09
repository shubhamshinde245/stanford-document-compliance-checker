.DEFAULT_GOAL := start

API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 3000

.PHONY: help install ensure-env start dev backend frontend

help:
	@echo "make install   Install Python and Node dependencies"
	@echo "make start     Create .env.local if needed, then start API and Next.js"
	@echo "make backend   Start FastAPI only"
	@echo "make frontend  Start Next.js only"

install:
	uv sync
	cd frontend && npm install

ensure-env:
	@if [ ! -f .env.local ] || ! grep -q '^AI_GATEWAY_API_KEY=' .env.local; then \
		cp .env.example .env.local; \
		echo "Created .env.local — paste AI_GATEWAY_API_KEY there."; \
	fi
	@if [ ! -f frontend/.env.local ]; then \
		cp frontend/.env.example frontend/.env.local; \
	fi

backend: ensure-env
	uv run uvicorn backend.main:app --reload --env-file .env.local --host $(API_HOST) --port $(API_PORT)

frontend: ensure-env
	cd frontend && npm run dev -- --port $(WEB_PORT)

start: ensure-env
	@echo "API  http://$(API_HOST):$(API_PORT)"
	@echo "Web  http://localhost:$(WEB_PORT)"
	@echo "Key  .env.local  (AI_GATEWAY_API_KEY)"
	@trap 'kill 0' EXIT INT TERM; \
		uv run uvicorn backend.main:app --reload --env-file .env.local --host $(API_HOST) --port $(API_PORT) & \
		cd frontend && npm run dev -- --port $(WEB_PORT)

dev: start
