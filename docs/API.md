# API.md
## Phase 8 - Core API & Module Reference

This document provides a technical API reference for the primary Python classes, methods, and functions in **Project Hermit** (`v0.1.9`).

---

### 1. `Orchestrator` & `StaticMCPHost` (`orchestrator.py`)

The primary host controller managing skill registration, baseline freezing, candidate verification, keypool quota tracking, and multi-objective Pareto scoring.

#### `register_or_update_skill(skill_name: str, description: str, code: str) -> bool`
* **Description**: Registers a new skill payload or updates an existing skill in `active_skills`. Computes SHA-256 baseline harness hash (`harness_hash`). Automatically skips immutable functions listed in `IMMUTABLE_FUNCTIONS`.
* **Parameters**:
  * `skill_name` (`str`): Unique identifier of the function.
  * `description` (`str`): Skill description and verification harness.
  * `code` (`str`): Python implementation source code.
* **Returns**: `bool` — `True` if successfully registered/updated; `False` if skipped or failed.

#### `patch_source_file_with_skill(skill_name: str, optimized_code: str) -> bool`
* **Description**: Performs self-patch introspection. If an optimized skill belongs to Project Hermit's own source files, it replaces the definition in place, creates a versioned backup, and executes `test_hermit.py`. Automatically rolls back on test failure.
* **Parameters**:
  * `skill_name` (`str`): Name of the self-patch function.
  * `optimized_code` (`str`): New optimized function code.
* **Returns**: `bool` — `True` if integrity tests passed and patch committed; `False` if rolled back.

#### `detect_oscillation(skill_name: str, window: int = 6) -> Tuple[bool, List[str]]`
* **Description**: Evaluates the last 6 merges in `version_history` for `skill_name` to detect repeated sequence cycles (e.g. `A-B-A-B` or `A-B-C-A-B-C`).
* **Parameters**:
  * `skill_name` (`str`): Target skill name.
  * `window` (`int`): Recency window size (default: 6).
* **Returns**: `Tuple[bool, List[str]]` — `(is_cycle_detected, list_of_banned_strategies)`.

---

### 2. `HermitDaemon` (`hermit_daemon.py`)

The autonomous background daemon controlling dual-phase target scheduling, predictive thermal management, and plateau auto-shutdown.

#### `get_next_target() -> Tuple[str, str]`
* **Description**: Implements the **Dual-Phase Scheduler**:
  * *Phase 1*: Targets untouched skills (0 merges) sorted by headroom (`latency × complexity`).
  * *Phase 2*: Targets high-latency bottleneck skills with a maximum consecutive cap (`MAX_CONSECUTIVE = 3`).
* **Returns**: `Tuple[str, str]` — `(target_skill_name, selected_strategy_mode)`.

#### `calculate_latency_slope(window_minutes: int = 20) -> float`
* **Description**: Performs linear regression on relative latency improvements over a rolling window. Used to trigger `GLOBAL_PLATEAU_SHUTDOWN` if slope improvement drops below 5%.
* **Parameters**:
  * `window_minutes` (`int`): Rolling window duration in minutes (default: 20).
* **Returns**: `float` — Improvement slope value.

---

### 3. `sandbox.py` Module

The isolated execution harness executing untrusted Python code inside RAM disk environments.

#### `run_in_sandbox(code_filepath: str, timeout: float = 30.0) -> SandboxResult`
* **Description**: Mounts `sandbox_run` as a 32MB `tmpfs` RAM disk, performs pre-execution static AST safety checks (`analyze_code_safety`), sets virtual memory bounds (`RLIMIT_AS`), and executes the candidate via fork-based grandchild process monitoring.
* **Parameters**:
  * `code_filepath` (`str`): Path to the python script to execute.
  * `timeout` (`float`): CPU time limit in seconds (default: 30.0).
* **Returns**: `SandboxResult` — Object containing `returncode`, `duration_ms`, `max_rss_kb`, `stdout`, and `stderr`.

#### `analyze_code_safety(code: str) -> Tuple[bool, str]`
* **Description**: Pre-execution AST static analyzer blocking forbidden module imports (`subprocess`, `requests`, `urllib`) or attribute calls (`os.system`, `eval`, `exec`).
* **Parameters**:
  * `code` (`str`): Python source code string.
* **Returns**: `Tuple[bool, str]` — `(is_safe, error_reason_if_unsafe)`.
