# CONFIGURATION.md
## Phase 9 - System Configuration & Environment Reference

This document details all environment variables, runtime parameters, default settings, feature flags, database schemas, and configuration files in **Project Hermit** (`v0.1.9`).

---

### 1. Environment Variables

| Variable | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `str` | `""` (Empty) | Primary Google GenAI API key for LLM-driven synthesis and research agent queries. |
| `HERMIT_DB_PATH` | `str` | `"hermit_memory.db"` | Path to the SQLite memory and telemetry database file. |
| `HERMIT_SANDBOX_DIR`| `str` | `"sandbox_run"` | Target directory mounted as a 32MB `tmpfs` RAM disk for sandbox execution. |
| `HERMIT_MODEL` | `str` | `"gemini-3.1-flash-lite"`| Default LLM model used for synthesis and optimization prompt generation. |

---

### 2. Runtime Thresholds & Default Parameters

#### Scheduler & Daemon Defaults (`hermit_daemon.py`)
* **Phase 1 Exploration Headroom**: `headroom = latency_ms × complexity_chars` (Sort order: `headroom DESC`).
* **Phase 2 Max Consecutive Limit**: `MAX_CONSECUTIVE = 3` attempts per skill before forcing queue rotation.
* **Stagnation Timeout**: `1 hour` without a merge triggers forced random exploration mode.
* **Global Plateau Shutdown Threshold**: Improvement slope < `5%` over a 20-minute rolling window (`calculate_latency_slope`).
* **Daemon Budget Caps**: `5,000,000` total tokens or `2 hours` total execution duration.

#### Sandbox Isolation & Resource Limits (`sandbox.py`)
* **CPU Time Limit (`RLIMIT_CPU`)**: `30.0 seconds`.
* **RAM Disk Mount Capacity**: `32MB` `tmpfs` memory buffer.
* **Virtual Memory Limit (`RLIMIT_AS`)**: Dynamic cap calculated as `Parent VmSize + 512MB`.
* **Verification Pacing Delay**: Mandatory `5.0 second` delay between outbound LLM API calls.

---

### 3. Database Schema Tables (`hermit_memory.db`)

* `active_skills`: Active skill registry (skill_name, version, code, description, baseline_latency, baseline_memory, harness_hash).
* `version_history`: Historical version releases and merge logs (id, timestamp, skill_name, version, strategy, latency_ms).
* `banned_strategies`: Temporarily banned optimization strategies (skill_name, strategy, cooldown_remaining).
* `skill_dependencies`: Call graph static dependency edges (skill_name, dependency_name).
* `skill_budgets`: Per-skill token and call budgets (skill_name, total_tokens, total_calls).
* `anti_patterns`: Syntactic and compilation failure patterns fed into prompt constraints.
* `scheduled_validations`: Introspection self-patch delayed rollback validation jobs.
