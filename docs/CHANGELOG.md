# CHANGELOG.md
## Release Changelog for Project Hermit

All notable changes, architectural pivots, and engine improvements to Project Hermit are documented in this file.

---

### [v0.1.9] - 2026-07-30 (Current Release)
#### Added
* **Fork-Based Grandchild Sandbox Memory Measurement**: Captures exact peak RSS per execution attempt, resolving cumulative `RUSAGE_CHILDREN` 0.0 KB RAM reporting.
* **6-Merge Sequence Cycle Detection**: Detects strategy recency patterns (`A-B-A-B`) to prevent false-positive strategy bans on newly merged versions.
* **Token Cost Budgeting (`skill_budgets`)**: Gated synthesis loops exceeding 500k tokens on complex untouched functions.
* **Database Integrity & Backups**: Startup integrity checks (`PRAGMA integrity_check`) and automated 30-minute `VACUUM INTO` snapshots.
* **Timezone Unification**: Standardized all logs, database entries, and thought ledgers under UTC timestamps.

---

### [v0.1.8] - 2026-06-28
#### Added
* **Dual-Phase Scheduling**: Phase 1 (untouched headroom) vs Phase 2 (bottleneck sort with `MAX_CONSECUTIVE = 3` cap).
* **Baseline Harness Freezing**: Freezes verification harness SHA-256 hashes (`HARNESS_DRIFT_ERROR`) to prevent baseline drift.

---

### [v0.1.7] - 2026-06-28
#### Added
* **AST Mathematical Mutator (`math_mutator.py`)**: Constant folding, algebraic simplification, and closed-form math substitutions.
* **Initial Strategy Banning**: Count-based strategy ban logic.

---

### [v0.1.6] - 2026-06-28
#### Added
* **RAM Disk Sandbox Isolation (`sandbox.py`)**: Executing candidates in 32MB `tmpfs` RAM disk with dynamic `RLIMIT_AS` memory bounds.

---

### [v0.1.5] - 2026-06-28
#### Added
* **Quantum-Classical QUBO Engine (`qubo_mutator.py`)**: Local $O(N)$ bitwise spin-flip delta energy updates.

---

### [v0.1.0] - 2026-06-27
#### Added
* **Decoupled Dynamic MCP Payload (`dynamic_mcp_server.py`)**: Decoupled target skills from host orchestrator for hot-reloading (`importlib.reload`).
