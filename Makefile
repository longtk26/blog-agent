SHELL := /bin/bash
COMPOSE_FILES := -f docker-compose.yml $(if $(BLOGS),-f docker-compose.blogs.yml)
# Use the Linux docker CLI when available; otherwise fall back to Docker Desktop's docker.exe
# (WSL without Docker Desktop's WSL integration). Override with `make up DOCKER=...`.
DOCKER_DESKTOP_EXE := /mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe
DOCKER ?= $(shell docker version >/dev/null 2>&1 && echo docker || { [ -x "$(DOCKER_DESKTOP_EXE)" ] && echo '"$(DOCKER_DESKTOP_EXE)"' || echo docker; })
COMPOSE := $(DOCKER) compose $(COMPOSE_FILES)

.env:
	@cp .env.example .env && echo "Created .env from .env.example — add your LLM / LangSmith keys, then re-run."

## ---- Docker (daily use) ---------------------------------------------------
up: .env ## Build and start db, api, ui (BLOGS=1 also mounts ../blogs)
	@mkdir -p data
	$(COMPOSE) up -d --build
	@echo "Dashboard: http://127.0.0.1:$${UI_PORT:-3100}   API: http://127.0.0.1:$${API_PORT:-8100}/docs"

down: ## Stop containers (data is kept)
	$(COMPOSE) down

logs: ## Follow logs (SERVICE=api to filter)
	$(COMPOSE) logs -f --tail=200 $(SERVICE)

ps:
	$(COMPOSE) ps

reset-db: ## Delete ALL tasks, revisions and checkpoints (asks first)
	@read -p "This permanently deletes the database volume. Type 'reset' to continue: " answer; \
	if [ "$$answer" = "reset" ]; then $(COMPOSE) down -v; else echo "Aborted."; fi

migrate: ## Apply migrations inside the running api container
	$(COMPOSE) exec api python -m alembic upgrade head

## ---- Hybrid dev (db in Docker, api + ui on the host with hot reload) -------
dev-db: .env
	$(COMPOSE) up -d db

dev-api:
	$(MAKE) -C api mghead run

dev-ui:
	@set -a; source .env; set +a; cd ui && AGENT_API_URL=http://127.0.0.1:$${API_PORT:-8100} pnpm dev

dev: dev-db ## Hot-reload API (8100) + UI (3100) against the Docker db
	$(MAKE) -j2 dev-api dev-ui

install: ## Install api (.venv) and ui (pnpm) dependencies for hybrid dev
	$(MAKE) -C api install
	cd ui && pnpm install

## ---- Quality --------------------------------------------------------------
test: ## API unit tests + UI typecheck/lint
	$(MAKE) -C api test-unit
	cd ui && pnpm check-types && pnpm lint

test-integration: dev-db ## API tests against a real Postgres (the compose db)
	@set -a; source .env; set +a; \
	$(COMPOSE) exec -T db sh -c "createdb -U $$POSTGRES_USER blog_agent_test 2>/dev/null || true"; \
	TEST_DB_URL=postgresql://$$POSTGRES_USER:$$POSTGRES_PASSWORD@127.0.0.1:$${DB_PORT:-5433}/blog_agent_test $(MAKE) -C api test

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

.PHONY: up down logs ps reset-db migrate dev-db dev-api dev-ui dev install test test-integration help
