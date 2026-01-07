# OpenCode Monitor - Makefile
#
# Native macOS menu bar app (rumps)

.PHONY: help run test test-unit test-integration test-integration-visible coverage coverage-html mutation mutation-browse mutation-clean test-audit clean roadmap

# Default target
help:
	@echo "OpenCode Monitor"
	@echo ""
	@echo "Usage:"
	@echo "  make run                    Run the menu bar app"
	@echo "  make test                   Run unit tests (excludes integration)"
	@echo "  make test-unit              Run unit tests only"
	@echo "  make test-integration       Run integration tests (headless)"
	@echo "  make test-integration-visible  Run integration tests (visible UI)"
	@echo "  make test-all               Run all tests (unit + integration)"
	@echo "  make coverage               Run tests with coverage report"
	@echo "  make coverage-html          Run tests with HTML coverage report"
	@echo ""
	@echo "Mutation Testing:"
	@echo "  make mutation               Run full mutation testing"
	@echo "  make mutation-mini          Quick test on utils module (~2min)"
	@echo "  make mutation-security      Test security/risk_analyzer (~5min)"
	@echo "  make mutation-debug         Test setup with single mutant"
	@echo "  make mutation-report        Run mutation + generate report"
	@echo "  make mutation-browse        Interactive mutation results browser"
	@echo "  make mutation-results       Show mutation test results"
	@echo "  make mutation-clean         Clean mutation cache"
	@echo ""
	@echo "Test Quality:"
	@echo "  make test-audit             Audit all test files"
	@echo "  make test-audit-file FILE=x Audit specific file"
	@echo "  make test-audit-priority    Audit priority files"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Remove temp/build files"
	@echo "  make roadmap        Show roadmap status"

# === Application ===

run:
	@uv run python -c "import sys; sys.path.insert(0, 'src'); from opencode_monitor.app import main; main()"

# === Testing ===

test:
	@uv run pytest tests/ -v -n 8 --ignore=tests/integration

test-unit:
	@uv run pytest tests/ -v -n 8 --ignore=tests/integration -m "not integration"

test-integration:
	@QT_QPA_PLATFORM=offscreen uv run pytest tests/integration/ -v -n 8 -m integration

test-integration-visible:
	@uv run pytest tests/integration/ -v -n 8 -m integration

test-all:
	@QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v -n 8

coverage:
	@uv run pytest tests/ -n 8 --cov=src/opencode_monitor --cov-report=term-missing

coverage-html:
	@uv run pytest tests/ -n 8 --cov=src/opencode_monitor --cov-report=html
	@open htmlcov/index.html

# === Mutation Testing ===
# Note: Uses pyproject.toml [tool.mutmut] config

mutation:
	@echo "Running full mutation testing (this takes a while)..."
	@uv run mutmut run

mutation-mini:
	@echo "Running quick mutation test on utils module..."
	@rm -f .mutmut-cache
	@uv run mutmut run "src/opencode_monitor/utils.py*"
	@uv run mutmut results

mutation-security:
	@echo "Running mutation test on security modules..."
	@rm -f .mutmut-cache
	@uv run mutmut run "src/opencode_monitor/security/risk_analyzer.py*"
	@uv run mutmut results

mutation-browse:
	@uv run mutmut browse

mutation-results:
	@uv run mutmut results

mutation-clean:
	@rm -rf mutants/ .mutmut-cache
	@echo "Mutation cache cleaned"

mutation-show:
	@uv run mutmut show $(MUTANT)

mutation-report:
	@./scripts/mutation-report.sh

mutation-debug:
	@echo "Testing mutation setup with single mutant..."
	@rm -f .mutmut-cache
	@uv run mutmut run "src/opencode_monitor/utils.py:1"
	@uv run mutmut results

# === Test Quality Audit ===

test-audit:
	@./scripts/test-audit.sh

test-audit-file:
	@./scripts/test-audit.sh $(FILE)

test-audit-priority:
	@echo "=== Priority Files (Low Assertion Ratio) ==="
	@./scripts/test-audit.sh "tests/test_hybrid_indexer_resume.py tests/test_unified_indexer.py tests/test_dashboard_sync.py tests/test_mitre_tags.py tests/test_tooltips.py tests/test_correlator.py"

# === Maintenance ===

clean:
	@rm -rf .coverage htmlcov/
	@rm -rf mutants/ .mutmut-cache
	@rm -rf src/*.egg-info
	@rm -rf __pycache__ src/__pycache__ tests/__pycache__
	@rm -rf src/opencode_monitor/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Build artifacts cleaned"

roadmap:
	@cat roadmap/README.md 2>/dev/null || echo "No roadmap found"
