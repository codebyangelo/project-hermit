# SPDX-License-Identifier: Apache-2.0
# Project Hermit: Autonomous Self-Evolving Code & Logic Engine

PYTHON ?= python3

.PHONY: all test verify lint format clean install daemon chat monitor mcp

all: verify

install:
	@echo "[*] Installing project-hermit in editable mode..."
	$(PYTHON) -m pip install -e .

test:
	@echo "[*] Running Project Hermit test suite..."
	PYTHONPATH=src:src/hermit $(PYTHON) -m unittest discover tests

lint:
	@echo "[*] Running ruff lint checks..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check src tests; \
	else \
		$(PYTHON) -m ruff check src tests 2>/dev/null || echo "[!] ruff not installed; skipping lint"; \
	fi

format:
	@echo "[*] Checking ruff formatting..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff format --check src tests; \
	fi

verify: test
	@echo "[+] ALL SYSTEMS VERIFIED: Autonomous scheduler, AST mutators, and sandbox passed cleanly."

daemon:
	@echo "[*] Launching Project Hermit Autonomous Daemon..."
	PYTHONPATH=src:src/hermit $(PYTHON) -m hermit.cli daemon

chat:
	@echo "[*] Launching Project Hermit Interactive Steering Console..."
	PYTHONPATH=src:src/hermit $(PYTHON) -m hermit.cli chat

monitor:
	@echo "[*] Launching Project Hermit Real-Time Monitor..."
	PYTHONPATH=src:src/hermit $(PYTHON) -m hermit.cli monitor

mcp:
	@echo "[*] Launching Project Hermit Dynamic MCP Server..."
	PYTHONPATH=src:src/hermit $(PYTHON) -m hermit.cli mcp

clean:
	@echo "[*] Cleaning build and temporary artifacts..."
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	rm -f hermit_memory_backup_*.db evolution_report_*.md
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
