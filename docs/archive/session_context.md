# Project Hermit: Session Context File (v0.1.9)

This file documents the implementations, execution logs, and architectural lessons from the current session to enable a seamless resumption of work in the next session.

---

## 📅 Session Summary
* **Active Version:** [v0.1.9](file:///root/home/projects/project-hermit/v0.1.9) (Branched from [v0.1.8](file:///root/home/projects/project-hermit/v0.1.8))
* **Main Requests:**
  1. Complete implementation of v0.1.9 plan.
  2. Implement measurement integrity & system hardening: true cycle oscillation detection, fork-based memory measurement, hierarchical class-weighted Pareto scoring, UTC timezone unification, cost budgets, database checks/backups, sandbox safety limits and static analysis, silent stagnation checks, and skill-class optimization adaptation.
  3. Ensure all tests run and pass.
* **Status:** **Completed & Verified.** All v0.1.9 implementations are verified via the unit test suite [test_hermit.py](file:///root/home/projects/project-hermit/v0.1.9/test_hermit.py) (17/17 tests passing successfully). Added `select_api_key` to `EXCLUDED_SKILLS` to protect API key selection infrastructure.

---

## 🛠️ Key Implementations in v0.1.9

1. **True Cycle Oscillation Detection ([orchestrator.py](file:///root/home/projects/project-hermit/v0.1.9/orchestrator.py)):**
   * Replaced simplistic count-based strategy banning with true sequence cycle detection (`A-B-A-B` or `A-B-C-A-B-C` patterns) over a recency window of 6 merges.
   * Eliminates the success-punishment bug where successful merges were immediately banned.
2. **Fork-Based Grandchild Sandbox Memory Measurement ([sandbox.py](file:///root/home/projects/project-hermit/v0.1.9/sandbox.py)):**
   * Spawns isolated execution subprocesses inside a fork-pipe grandchild architecture.
   * Gets the exact peak RSS of individual runs cleanly using `resource.getrusage(resource.RUSAGE_CHILDREN)` in the fork child, resolving the `0 KB` RAM reporting bug.
3. **Hierarchical, Domain-Aware Pareto Scoring ([orchestrator.py](file:///root/home/projects/project-hermit/v0.1.9/orchestrator.py)):**
   * Classifies skills (e.g. `parser`, `search`, `io_bound`, `general`) and maps class-weighted scores.
   * Employs hierarchical Pareto gates (latency gate, memory guard, complexity tiebreaker) to prevent regression merges.
4. **Sandbox Hardening & Pre-Execution Safety ([sandbox.py](file:///root/home/projects/project-hermit/v0.1.9/sandbox.py)):**
   * Enforces CPU time limits (30s) and dynamic virtual memory limits (`RLIMIT_AS` set dynamically based on parent VmSize + 512MB) inside sandbox executions.
   * Statically checks code syntax using AST (`analyze_code_safety`) to block dangerous imports (e.g., `subprocess`, `requests`, `socket`, `urllib`) or attributes.
5. **Token Cost Budget Gates ([orchestrator.py](file:///root/home/projects/project-hermit/v0.1.9/orchestrator.py) / [hermit_daemon.py](file:///root/home/projects/project-hermit/v0.1.9/hermit_daemon.py)):**
   * Tracks per-skill API token consumption and calls in `skill_budgets`.
   * Gates out attempts exceeding 500K tokens unless they have > 10 merges, marking them as explored to prevent expensive synthesis loops.
6. **Database Integrity & Backups ([orchestrator.py](file:///root/home/projects/project-hermit/v0.1.9/orchestrator.py)):**
   * Checks database health on startup (`PRAGMA integrity_check`) and triggers automated `VACUUM INTO` backups every 30 minutes, keeping only the 5 most recent backups.
7. **Silent Stagnation Check ([hermit_daemon.py](file:///root/home/projects/project-hermit/v0.1.9/hermit_daemon.py)):**
   * Periodically checks if the daemon is stagnant (no merges for > 1 hour) and automatically forces exploration of random/new skills.
8. **Timezone Unification ([logger.py](file:///root/home/projects/project-hermit/v0.1.9/logger.py) / [orchestrator.py](file:///root/home/projects/project-hermit/v0.1.9/orchestrator.py) / [observer.py](file:///root/home/projects/project-hermit/v0.1.9/observer.py)):**
   * Unified all timestamps across logs, thoughts ledger, database records, and reports to UTC.

---

## 📊 Telemetry & Dissection Findings (v0.1.9)

*   **Memory Accuracy Verification:** Verified that `mem_test.py` allocates buffers and correctly logs non-zero RSS change (e.g., `64732 KB`), resolving the `0 KB` baseline bug.
*   **Sandbox Safety Verification:** Pre-execution check successfully blocked imports of `subprocess` and calls to `os.system` with exit code `-3` during unit tests.
*   **Pareto Dominance Enforcement:** Successfully rejected latency regression candidates (e.g., `110.0 ms` vs `100.0 ms` baseline) and memory regression candidates during tests.
*   **Backups Collision Avoidance:** Replaced standard timestamp backups with high-resolution microseconds format `%Y%m%d_%H%M%S_%f` to prevent SQLite write conflicts during fast-paced concurrent testing.

---

## 📅 Architectural Lessons Learned

*   **Process Isolation for Resource Limits**: Using `os.fork()` to execute subprocesses in Unix provides a clean, independent child process context. This enables accurate measurement of individual peak RSS via `RUSAGE_CHILDREN` without polluting the parent process stats.
*   **Static AST Security Screening**: Analyzing AST before execution is a lightweight, zero-overhead way to enforce safety policies in code generation architectures, rejecting risky mutations before sandbox execution.
*   **Parent-Relative VM Limits**: Setting `RLIMIT_AS` (Virtual Memory limit) to a fixed hard cap (like 512MB) can crash runtimes like Python in nested VM/Proot/emulated environments because of huge host mapping sizes. Limits should always be calculated dynamically relative to the parent's actual startup VM size.

---

## 📜 Unified Session Update Rule
> **Contract Directive**: Whenever ending a session and updating a context file (e.g., `/root/session_context.md`, `/root/home/projects/project-hermit/session_context.md`, or other project-level context files), the agent must check if any code modifications were made. If changes were made, the agent must update the project's README.md files accordingly to ensure they align with the latest codebase state.
