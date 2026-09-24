# UniFi MCP Server - developer workflow
#
# Every target runs its tool through uv against the locked dev environment,
# so no virtualenv activation is needed. `make ci` runs the same blocking
# checks as .github/workflows/ci.yml.
#
# Without uv, install with `pip install -e ".[dev]"` in an active virtualenv
# and pass an empty runner:  make test RUN=

UV            ?= uv
RUN           ?= $(UV) run --frozen --extra dev
SRC           := src/
TESTS         := tests/
IMAGE         ?= unifi-mcp-server
TAG           ?= dev
COVERAGE_MIN  ?= 80
# Hooks the CI pre-commit job skips: mypy runs in `typecheck`, the rest are cosmetic.
PRECOMMIT_SKIP ?= mypy,end-of-file-fixer,markdownlint

.DEFAULT_GOAL := help

##@ Setup

.PHONY: install
install: ## Create .venv from uv.lock with the dev extra
	$(UV) sync --frozen --extra dev

.PHONY: hooks
hooks: ## Install the git pre-commit and commit-msg hooks
	$(RUN) pre-commit install --hook-type pre-commit --hook-type commit-msg

##@ Quality

.PHONY: format
format: ## Format code with black and isort
	$(RUN) black $(SRC) $(TESTS)
	$(RUN) isort $(SRC) $(TESTS)

.PHONY: lint
lint: ## Check formatting, import order, and lint (CI "Lint and Format Check")
	$(RUN) black --check $(SRC) $(TESTS)
	$(RUN) isort --check-only $(SRC) $(TESTS)
	$(RUN) ruff check $(SRC) $(TESTS)

.PHONY: typecheck
typecheck: ## Type check with mypy (non-blocking in CI: pre-existing errors)
	$(RUN) mypy $(SRC)

.PHONY: security
security: ## Scan source with bandit, medium severity and up (CI "Security Checks")
	$(RUN) bandit -r $(SRC) -ll -q

.PHONY: audit
audit: ## Check installed dependencies for known vulnerabilities
	$(RUN) pip-audit

.PHONY: docs-coverage
docs-coverage: ## Check docstring coverage of tools and API client (CI "Documentation Coverage")
	$(RUN) interrogate src/tools/ src/api/ --fail-under 80

.PHONY: pre-commit
pre-commit: ## Run all pre-commit hooks on every file, skipping the ones CI skips
	SKIP=$(PRECOMMIT_SKIP) $(RUN) pre-commit run --all-files

##@ Tests

.PHONY: test
test: ## Run the unit tests
	$(RUN) pytest tests/unit/ -q

.PHONY: test-cov
test-cov: ## Run non-integration tests with the CI coverage gate
	$(RUN) pytest $(TESTS) -m "not integration" --cov=src --cov-report=xml \
		--cov-report=term-missing --cov-fail-under=$(COVERAGE_MIN)

.PHONY: ci
ci: lint security docs-coverage pre-commit test-cov ## Run every blocking CI check locally

##@ Run

.PHONY: run
run: ## Start the MCP server (reads configuration from .env)
	$(UV) run --frozen unifi-mcp-server

.PHONY: inspect
inspect: ## Open the server in the MCP Inspector (needs Node.js)
	npx @modelcontextprotocol/inspector $(UV) run --frozen unifi-mcp-server

##@ Docker

.PHONY: docker-build
docker-build: ## Build the Docker image (IMAGE=unifi-mcp-server TAG=dev by default)
	docker build -t $(IMAGE):$(TAG) .

.PHONY: compose-up
compose-up: ## Start the docker-compose stack in the background
	docker compose up -d

.PHONY: compose-down
compose-down: ## Stop the docker-compose stack
	docker compose down

.PHONY: compose-logs
compose-logs: ## Follow the MCP server container logs
	docker compose logs -f unifi-mcp

##@ Housekeeping

.PHONY: clean
clean: ## Remove caches, coverage output, and build artifacts (keeps .venv)
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml \
		bandit-report.json dist build *.egg-info

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n"} \
		/^##@/ {printf "\n%s\n", substr($$0, 5)} \
		/^[a-zA-Z_-]+:.*##/ {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
