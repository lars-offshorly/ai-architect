.PHONY: install run dev test test-unit test-integration lint format lint-file lint-staged lint-mr check-mr validate-templates generate-template seed help

POETRY := poetry
POETRY_QUIET := env PYTHONWARNINGS="ignore::Warning" $(POETRY)
SRC_DIR := src
TEST_DIR := tests
LINT_PATHS := src tests onboarding catalog scripts
FLAKE8_FLAGS := --max-line-length=88
PYLINT_FLAGS := --disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

export PYTHONPATH := $(SRC_DIR):.

help:
	@echo "Available targets:"
	@echo "  install               Install dependencies with Poetry (including dev)"
	@echo "  run                   Start the API server (production mode)"
	@echo "  dev                   Start the API server with hot reload"
	@echo "  test                  Run all tests"
	@echo "  test-unit             Run unit tests only"
	@echo "  test-integration      Run integration tests only"
	@echo "  lint                  Run black + ruff + flake8 + mypy + pylint + vulture"
	@echo "  format                Run black + ruff formatter"
	@echo "  lint-file             Lint specific file(s) or directory (usage: make lint-file src/foo.py tests/test_bar.py)"
	@echo "  lint-staged           Lint staged Python files"
	@echo "  lint-mr               Lint changed Python files vs dev branch"
	@echo "  check-mr              Run tests + lint changed Python files vs dev branch"
	@echo "  validate-templates    Validate all bundle template JSON files"
	@echo "  generate-template     Scaffold a new bundle (usage: make generate-template BUNDLE=my_bundle)"
	@echo "  seed BUNDLE=<key>     Print dummy data for a bundle to stdout"

install:
	$(POETRY) install --with dev

run:
	PYTHONPATH=$(SRC_DIR) $(POETRY) run uvicorn main:app --host 0.0.0.0 --port 8000

dev:
	PYTHONPATH=$(SRC_DIR) $(POETRY) run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

test:
	PYTHONPATH=$(SRC_DIR):. $(POETRY) run pytest $(TEST_DIR) -v --tb=short --continue-on-collection-errors || true
	@echo "\n========== TEST SUMMARY =========="
	@echo "Tests completed. Check output above for pass/fail details."

test-unit:
	PYTHONPATH=$(SRC_DIR):. $(POETRY) run pytest $(TEST_DIR)/unit -v --tb=short --continue-on-collection-errors || true
	@echo "\n========== TEST SUMMARY =========="
	@echo "Unit tests completed. Check output above for pass/fail details."

test-integration:
	PYTHONPATH=$(SRC_DIR):. $(POETRY) run pytest $(TEST_DIR)/integration -v --tb=short --continue-on-collection-errors || true
	@echo "\n========== TEST SUMMARY =========="
	@echo "Integration tests completed. Check output above for pass/fail details."

lint:
	@echo "black..."
	@$(POETRY_QUIET) run black $(LINT_PATHS)
	@echo "ruff..."
	@$(POETRY_QUIET) run ruff check $(LINT_PATHS)
	@echo "flake8..."
	@$(POETRY_QUIET) run flake8 $(LINT_PATHS) $(FLAKE8_FLAGS) --count
	@echo "mypy..."
	@$(POETRY_QUIET) run mypy $(LINT_PATHS)
	@echo "pylint..."
	@$(POETRY_QUIET) run pylint $(LINT_PATHS) $(PYLINT_FLAGS)
	@echo "vulture..."
	@$(POETRY_QUIET) run vulture $(LINT_PATHS) --min-confidence 90

format:
	@echo "black..."
	@$(POETRY) run black $(LINT_PATHS)
	@echo "ruff format..."
	@$(POETRY) run ruff format $(LINT_PATHS)

# Usage: make lint-file src/api/endpoints.py tests/test_api.py
# Usage: make lint-file src/api/
lint-file:
	@if [ -z "$(filter-out $@,$(MAKECMDGOALS))" ]; then \
		echo "Usage: make lint-file file1.py [file2.py ...] or make lint-file directory/"; \
		exit 1; \
	fi
	@echo "Linting files: $(filter-out $@,$(MAKECMDGOALS))"
	@echo "black..."
	@$(POETRY_QUIET) run black $(filter-out $@,$(MAKECMDGOALS))
	@echo "ruff..."
	@$(POETRY_QUIET) run ruff check $(filter-out $@,$(MAKECMDGOALS))
	@echo "flake8..."
	@$(POETRY_QUIET) run flake8 $(filter-out $@,$(MAKECMDGOALS)) $(FLAKE8_FLAGS)
	@echo "mypy..."
	@$(POETRY_QUIET) run mypy $(filter-out $@,$(MAKECMDGOALS))
	@echo "pylint..."
	@$(POETRY_QUIET) run pylint $(filter-out $@,$(MAKECMDGOALS)) $(PYLINT_FLAGS)

# Allow passing arguments to lint-file without escaping
%:
	@:

lint-staged:
	@echo "Formatting and linting staged Python files..."
	@FILES=$$(git diff --cached --name-only --diff-filter=ACMR -- '*.py' | \
		grep -E '^(src/|tests/|onboarding/|catalog/|scripts/)' | \
		grep -v __pycache__ | \
		awk '{if (system("[ -f \"" $$0 "\" ]") == 0) print $$0}'); \
	if [ -z "$$FILES" ]; then \
		echo "No staged Python files to lint"; \
	else \
		echo "Files to process: $$FILES"; \
		echo "black..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run black; \
		echo "ruff..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run ruff check; \
		echo "flake8..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run flake8 $(FLAKE8_FLAGS); \
		echo "mypy..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run mypy; \
		echo "pylint..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run pylint $(PYLINT_FLAGS); \
		echo "vulture..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run vulture --min-confidence 90; \
	fi

lint-mr:
	@echo "Formatting and linting committed (vs origin/dev) and staged Python files..."
	@FILES=$$( { \
		git diff --name-only origin/dev...HEAD -- '*.py' 2>/dev/null; \
		git diff --cached --name-only --diff-filter=ACMR -- '*.py'; \
	} | \
		sort -u | \
		grep -E '^(src/|tests/|onboarding/|catalog/|scripts/)' | \
		grep -v __pycache__ | \
		awk '{if (system("[ -f \"" $$0 "\" ]") == 0) print $$0}'); \
	if [ -z "$$FILES" ]; then \
		echo "No existing Python files to lint"; \
	else \
		echo "Files to process: $$FILES"; \
		echo "black..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run black; \
		echo "ruff..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run ruff check; \
		echo "flake8..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run flake8 $(FLAKE8_FLAGS); \
		echo "mypy..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run mypy; \
		echo "pylint..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run pylint $(PYLINT_FLAGS); \
		echo "vulture..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run vulture --min-confidence 90; \
	fi

check-mr:
	@echo "========== RUNNING TESTS =========="
	PYTHONPATH=$(SRC_DIR):. $(POETRY) run pytest -v --tb=short --continue-on-collection-errors || true
	@echo "\n========== TESTS COMPLETED =========="
	@echo "Formatting and linting committed (vs origin/dev) and staged Python files..."
	@FILES=$$( { \
		git diff --name-only origin/dev...HEAD -- '*.py' 2>/dev/null; \
		git diff --cached --name-only --diff-filter=ACMR -- '*.py'; \
	} | \
		sort -u | \
		grep -E '^(src/|tests/|onboarding/|catalog/|scripts/)' | \
		grep -v __pycache__ | \
		awk '{if (system("[ -f \"" $$0 "\" ]") == 0) print $$0}'); \
	if [ -z "$$FILES" ]; then \
		echo "No existing Python files to lint"; \
	else \
		echo "Files to process: $$FILES"; \
		echo "black..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run black; \
		echo "ruff..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run ruff check; \
		echo "flake8..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run flake8 $(FLAKE8_FLAGS); \
		echo "mypy..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run mypy; \
		echo "pylint..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run pylint $(PYLINT_FLAGS); \
		echo "vulture..."; \
		echo "$$FILES" | xargs $(POETRY_QUIET) run vulture --min-confidence 90; \
	fi

validate-templates:
	$(POETRY) run python scripts/validate_templates.py

generate-template:
	@if [ -z "$(BUNDLE)" ]; then echo "Usage: make generate-template BUNDLE=<bundle_key>"; exit 1; fi
	$(POETRY) run python scripts/generate_templates.py $(BUNDLE)

seed:
	@if [ -z "$(BUNDLE)" ]; then echo "Usage: make seed BUNDLE=<bundle_key>"; exit 1; fi
	$(POETRY) run python scripts/seed_dummy_data.py $(BUNDLE)
