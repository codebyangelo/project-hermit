# Project Hermit v0.0.1 - Sandbox Foundation & Orchestrator Baseline

Version `v0.0.1` establishes the core sandboxing environment and local registry components for the Project Hermit optimization engine.

## Core Features
1. **Sandbox Execution (`sandbox.py`):**
   * Executes code variants inside a temporary, isolated sub-folder (`sandbox_run/`).
   * Measures execution time and tracks peak resident set size (max RSS) change via Python's native `resource` module.
   * Logs execution outcomes (`PASS` or `FAIL`) and metrics to the database.

2. **Skill Registry Orchestrator (`orchestrator.py`):**
   * Implements initial SQLite registry (`active_skills` and `reality_tests` tables) for tracking optimized versions.
   * Standardizes interaction with LLM models using direct interactions API calls.

3. **Core Verification Suite (`test_hermit.py`):**
   * Native unit tests validating isolated execution, memory tracking, and basic SQLite telemetry.

## Setup & Testing
To run the local sandbox unit tests:
```bash
python3 -m unittest test_hermit.py
```
