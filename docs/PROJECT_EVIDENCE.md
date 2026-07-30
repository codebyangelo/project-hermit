# PROJECT_EVIDENCE.md
## Pass A - Evidence Extraction Log for Project Hermit

This document contains only factual quotes, directory structures, version histories, schema definitions, and empirical benchmark observations extracted directly from the `project-hermit-git` codebase.

---

### 1. General Project Inventory & Root Structure

* **Root Path:** `/root/home/projects/project-hermit-git`
* **Subdirectory Count:** 20 main directories (`v0.0.1` through `v0.1.9`, plus `project_hermit_documentation`).
* **Total File Count:** 1,157 files.
* **File Breakdown by Extension:**
  * `.md`: 600 files (Evolution reports, planning documents, dissect reports, READMEs)
  * `.py`: 270 files (Engine components, AST mutators, test suites, evaluation scripts)
  * `.pyc`: 218 compiled bytecode files
  * `.db`: 26 SQLite database files (Memory state, benchmark metrics, history backups)
  * `.log`: 19 log files (Daemon logs, execution records)
  * `.txt`: 18 text files (API key pools, thoughts ledgers)
  * `.json`: 4 JSON configuration files
  * `.img`: 2 binary disk images (Sandbox adversarial test images)

---

### 2. File & Module Structure by Evolution Phase

#### Core Module Files (Present in `v0.1.9`):
* `orchestrator.py`: `StaticMCPHost` controller, API keypool manager, baseline hash freezing, candidate verification, cycle oscillation detection.
* `hermit_daemon.py`: Autonomous daemon scheduler (Phase 1 untouched headroom vs Phase 2 bottleneck sort), linear regression plateau shutdown, predictive thermal manager.
* `sandbox.py`: RAM-disk isolated sandbox execution engine (`tmpfs` RAM disk mount, AST safety checks, resource limit enforcement).
* `dynamic_mcp_server.py`: Decoupled dynamic MCP server payload holding target skills for dynamic mutation and runtime reloading (`importlib.reload`).
* `math_mutator.py`: Mathematical AST mutation engine (constant folding, algebraic simplification).
* `qubo_mutator.py`: Quantum-classical QUBO optimization engine (local bitwise spin-flip delta updates).
* `researcher.py` / `run_researcher_demo.py`: Autonomous research agent component.
* `observer.py`: System resource and performance observer.
* `analyze.py`: Log and memory introspection script.
* `logger.py`: Centralized structured logger with UTC timestamping.
* `init_db.py`: Database schema initialization and schema migration tool.
* `monitor_evolution.py`: CLI monitor for real-time tracking of daemon performance.
* `hermit_chat.py`: Interactive CLI interface for interacting with the Hermit system.

#### Test Suite Files (Present in `v0.1.9`):
* `test_hermit.py`: Comprehensive system integration test suite (17 tests passing cleanly).
* `test_integration.py`: Dynamic reload and payload execution test.
* `test_math_mutator.py`: AST mathematical mutation unit tests.
* `test_math_integration.py`: End-to-end math optimization integration test.
* `test_qubo_mutator.py`: AST spin-flip QUBO unit tests.
* `test_qubo_integration.py`: QUBO optimization integration test.
* `test_researcher.py`: Autonomous researcher unit test suite.
* `test_key_rotation.py`: Quota-aware API keypool rotation unit tests.
* `test_observer.py`: Performance and metric observer unit tests.

---

### 3. Database Schema Evidence (`v0.1.9/hermit_memory.db`)

Direct SQLite table extraction from `v0.1.9/hermit_memory.db`:
* **Active Tables (15):**
  1. `active_skills`: 124 rows (Tracks registered functions, baseline latency, baseline memory, harness hashes)
  2. `skill_branches`: 1,365 rows (Stores mutated code candidates, scores, metrics, parent lineage)
  3. `version_history`: 7 rows (Tracks merged version releases with strategy names and benchmark results)
  4. `banned_strategies`: 5 rows (Tracks strategies blocked by cycle oscillation detection)
  5. `skill_dependencies`: 44 rows (Tracks static dependency graph edges between skills for regression testing)
  6. `skill_budgets`: 4 rows (Per-skill API token consumption and budget limits)
  7. `limit_telemetry`: 1,804 rows (Execution resource telemetry data)
  8. `reality_tests`: 2,777 rows (Sandbox verification execution records)
  9. `adversarial_tests`: 258 rows (Adversarial edge-case verification tests)
  10. `user_interventions`: 12 rows (Logged user manual control interventions)
  11. `daemon_status`: 1 row (Daemon state, current phase, run cycle counter)
  12. `skill_research_notes`: 1 row (Notes generated during research phase)
  13. `anti_patterns`: 0 rows (Persistent AST/syntactic anti-patterns blocked in prompts)
  14. `scheduled_validations`: 0 rows (Self-patch rollback tracking entries)
  15. `sqlite_sequence`: 8 rows (Internal autoincrement sequence state)

---

### 4. Direct Empirical Benchmark Findings (`answers_to_questions_for_kimi.md`)

* **Active Skills Count:** 115 active skills evaluated in v0.1.8 dissection.
* **Top 3 Merge Concentration (v0.1.8):** 80.1% of all merges concentrated in 3 skills (`hex_search`: 74 merges, `scan_allowlist`: 51 merges, `parse_ip_port`: 36 merges).
* **Gini Coefficient (Merge distribution):** `0.9650`
* **Untouched Skill Count (v0.1.8 baseline):** 103 out of 115 skills (89.6% zero merges).
* **Token Cost per Merge (v0.1.8 second session):** `91,601 tokens/merge` across 39 API calls per merge.
* **RAM Measurement Anomaly:** `max_rss_kb` computed via `usage_end.ru_maxrss - usage_start.ru_maxrss` using `resource.RUSAGE_CHILDREN` led to `0.0 KB` RAM reporting when child processes did not exceed historical peak RSS.
