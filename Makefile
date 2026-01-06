# OpenCode Monitor - Makefile
#
# Native macOS menu bar app (rumps)

.PHONY: help run test test-unit test-integration test-integration-visible coverage coverage-html clean roadmap

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
	@echo "Maintenance:"
	@echo "  make clean          Remove temp/build files"
	@echo "  make roadmap        Show roadmap status"

# === Application ===

run:
	@uv run python -c "import sys; sys.path.insert(0, 'src'); from opencode_monitor.app import main; main()"

# === Testing ===

test:
	@uv run python -m pytest tests/ -v -n auto --ignore=tests/integration

test-unit:
	@uv run python -m pytest tests/ -v -n auto --ignore=tests/integration -m "not integration"

test-integration:
	@QT_QPA_PLATFORM=offscreen uv run python -m pytest tests/integration/ -v -n auto -m integration

test-integration-visible:
	@uv run python -m pytest tests/integration/ -v -n auto -m integration

test-all:
	@QT_QPA_PLATFORM=offscreen uv run python -m pytest tests/ -v -n auto

coverage:
	@uv run python -m pytest tests/ -n auto --cov=src/opencode_monitor --cov-report=term-missing

coverage-html:
	@uv run python -m pytest tests/ -n auto --cov=src/opencode_monitor --cov-report=html
	@open htmlcov/index.html

# === Maintenance ===

clean:
	@rm -rf .coverage htmlcov/
	@rm -rf src/*.egg-info
	@rm -rf __pycache__ src/__pycache__ tests/__pycache__
	@rm -rf src/opencode_monitor/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Build artifacts cleaned"

roadmap:
	@cat roadmap/README.md 2>/dev/null || echo "No roadmap found"
