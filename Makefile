.DEFAULT_GOAL := help
.PHONY: help dev env test test-all lint format up up-core down logs ps clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

dev: env ## Set up the dev environment (venv, deps, hooks)
	uv sync --all-groups
	uv run pre-commit install
	@echo
	@echo "Ready. \`make up\` starts the stack, \`make test\` runs the suite."

env: ## Create or top up .env, generating any missing secrets
	@./scripts/init_env.sh

test: ## Run the tests that do not need the dataset
	uv run pytest -m "not data"

test-all: ## Run everything, including tests that read data/docile
	uv run pytest

lint: ## Check formatting and lint
	uv run ruff format --check .
	uv run ruff check .

format: ## Fix what can be fixed automatically
	uv run ruff format .
	uv run ruff check --fix .

up: ## Start the whole stack, Langfuse included
	docker compose up -d
	@echo "Langfuse: http://localhost:$${LANGFUSE_PORT:-3000}"

up-core: ## Start only Postgres and Redis (skips the four Langfuse containers)
	docker compose up -d postgres redis

down: ## Stop the stack, keeping data
	docker compose down

logs: ## Follow logs (make logs s=langfuse-web for one service)
	docker compose logs -f $(s)

ps: ## Show service status
	docker compose ps

clean: ## Stop the stack and delete its volumes — all local data goes
	@printf 'Deletes every database and trace in the local stack. Type yes: ' \
		&& read ans && [ "$$ans" = yes ]
	docker compose down -v
