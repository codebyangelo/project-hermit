# PROJECT_MANIFEST.md
## Phase 0 - Project Inventory Manifest

This document records the exact structure, technology stack, dependencies, configuration files, test suites, and inventory metrics of **Project Hermit** (`project-hermit-git`).

---

### 1. General Project Information

* **Project Name:** Project Hermit
* **Target Directory:** `project-hermit-git`
* **Current Version:** `v0.1.9`
* **Architecture Style:** Autonomous Self-Evolving Multi-Agent System & Dynamic MCP Tool Host
* **Primary Language:** Python 3.10+ (tested with Python 3.13)
* **Storage Backend:** SQLite 3 (`hermit_memory.db`)

---

### 2. File & Extension Distribution

| Metric / Extension | Details / Count |
| :--- | :--- |
| **Total Root Files** | 1,157 |
| **Total Version Directories** | 19 (`v0.0.1` through `v0.1.9`) |
| `.md` Documentation Files | 600 files |
| `.py` Python Source Files | 270 files |
| `.pyc` Python Bytecode Files | 218 files |
| `.db` SQLite Database Files | 26 files |
| `.log` Log Files | 19 files |
| `.txt` Text & Key Files | 18 files |
| `.json` JSON Config Files | 4 files |
| `.img` Disk Images | 2 files |

---

### 3. Key Subdirectory Manifest

| Directory Name | File Count | Purpose / Description |
| :--- | :---: | :--- |
| `v0.1.9/` | 161 files | Active development release (v0.1.9 engine, test suite, database) |
| `v0.1.8/` | 153 files | Previous release ( fairness quota, baseline harness freezing) |
| `v0.1.7/` | 146 files | Previous release (AST math mutator, initial cycle detection) |
| `v0.1.6/` | 136 files | Previous release (RAM disk sandbox isolation engine) |
| `v0.1.5/` | 51 files | Early release (QUBO & quantum-classical engine integration) |
| `v0.1.4/` | 50 files | Early release (Initial decoupled dynamic MCP server payload) |
| `v0.1.3/` | 32 files | Early release (Initial database schema & version history) |
| `v0.1.2/` to `v0.0.1/` | 155 files | Historical incremental iteration snapshots |
| `project_hermit_documentation/` | 4 files | Archived legacy design notes and specs |

---

### 4. Code Base Components (v0.1.9)

#### Core Engine System
* [orchestrator.py](../v0.1.9/orchestrator.py): Host controller, key rotation, harness verification, cycle detection.
* [hermit_daemon.py](../v0.1.9/hermit_daemon.py): Scheduler daemon (Phase 1 untouched vs Phase 2 bottleneck), plateau auto-shutdown.
* [sandbox.py](../v0.1.9/sandbox.py): RAM-disk (`tmpfs`) isolated execution harness with grandchild fork memory measurement and safety AST parser.
* [dynamic_mcp_server.py](../v0.1.9/dynamic_mcp_server.py): Payload repository hosting target mutable skills.
* [math_mutator.py](../v0.1.9/math_mutator.py): Mathematical constant-folding and AST simplification engine.
* [qubo_mutator.py](../v0.1.9/qubo_mutator.py): Quantum-classical quadratic optimization engine.
* [researcher.py](../v0.1.9/researcher.py): Autonomous researcher module.
* [observer.py](../v0.1.9/observer.py): System resource metric monitor.
* [logger.py](../v0.1.9/logger.py): UTC-synchronized logging engine.
* [init_db.py](../v0.1.9/init_db.py): SQLite schema initialization and migration script.

#### Test Suites (100% Passing Status)
* [test_hermit.py](../v0.1.9/test_hermit.py): Main integration test suite (17 tests).
* [test_integration.py](../v0.1.9/test_integration.py): Dynamic MCP server module reloading test.
* [test_math_mutator.py](../v0.1.9/test_math_mutator.py): Math AST mutator unit tests.
* [test_math_integration.py](../v0.1.9/test_math_integration.py): End-to-end math mutator validation.
* [test_qubo_mutator.py](../v0.1.9/test_qubo_mutator.py): QUBO spin-flip unit tests.
* [test_qubo_integration.py](../v0.1.9/test_qubo_integration.py): QUBO engine integration test.
* [test_researcher.py](../v0.1.9/test_researcher.py): Research agent unit tests.
* [test_key_rotation.py](../v0.1.9/test_key_rotation.py): Quota-aware keypool rotation test.
* [test_observer.py](../v0.1.9/test_observer.py): Metric observer tests.

---

### 5. Dependency & Configuration Inventory

* **External Python Libraries:** `google-genai` / `google-generativeai`, `sqlite3`, `ast`, `resource`, `psutil`
* **Configuration Files:** `api_keys.txt` (Quota-aware multi-key pool), `plan_v0.1.9.md`
* **Data Assets & Databases:** `hermit_memory.db` (Primary memory store), `hermit_memory_backup_*.db` (Automated 30-min system snapshots)
