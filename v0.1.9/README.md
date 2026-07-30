# Project Hermit v0.1.9 - Measurement Integrity & System Hardening

Version `v0.1.9` introduces true period-based cycle oscillation detection, fork-based memory measurement (replacing cumulative `RUSAGE_CHILDREN`), hierarchical class-weighted Pareto scoring, UTC timezone unification, cost-per-merge token tracking and budgets, startup database integrity checks with automated backups, sandbox safety limits and static analysis, silent stagnation checks, and skill-class optimization adaptation.

## New in v0.1.9

1. **True Cycle Oscillation Detection:**
   * Replaced simplistic count-based strategy banning with true sequence cycle detection (`A-B-A-B` or `A-B-C-A-B-C` patterns) over a recency window of 6 merges, eliminating the success-punishment bug.

2. **Fork-Based Grandchild Sandbox Memory Measurement:**
   * Replaced cumulative `RUSAGE_CHILDREN` checks with a fork-based grandchild model. This allows fetching the exact peak RSS of individual runs cleanly, resolving the `0 KB` RAM reporting bug.

3. **Hierarchical, Domain-Aware Pareto Scoring:**
   * Integrates configurable multi-objective weights per skill class. Compares candidates against baseline metrics hierarchically (latency gate, memory guard, complexity tiebreaker) to prevent regression merges.

4. **Sandbox Hardening & Safety:**
   * Enforces CPU time limits (30s) and dynamic virtual memory limits (`RLIMIT_AS` set dynamically based on parent VmSize + 512MB) inside sandbox executions.
   * Performs pre-execution static AST analysis (`analyze_code_safety`) to block dangerous imports (e.g. `subprocess`, `requests`) or attributes.

5. **Token Cost Budget Gates:**
   * Tracks per-skill API token consumption and calls in `skill_budgets`. Prevents expensive synthesis loops on highly complex untouched skills by gating out attempts exceeding 500K tokens unless they have > 10 merges.

6. **Database Integrity & Backups:**
   * Checks database health on startup (`PRAGMA integrity_check`) and automatically triggers `VACUUM INTO` backups every 30 minutes, keeping only the 5 most recent backups.

7. **Timezone Unification:**
   * Unifies timestamps across logs, thoughts ledger, and database records to UTC.

8. **Silent Stagnation Check:**
   * Periodically checks if the daemon is stagnant (no merges for > 1 hour) and automatically forces exploration of random/new skills.

## Core Features

1. **Decoupled Mutable Tool Payload (`dynamic_mcp_server.py`):**
   * Acts as the registry target for self-evolution, mutating tools without interrupting host execution.

2. **Static Host Controller (`orchestrator.py` / `StaticMCPHost`):**
   * Houses the protected engine layer with dynamic context hot-reloading via `importlib.reload`.
   * Enforces strict framework protection via `EXCLUDED_SKILLS` whitelist (which now includes `select_api_key` to protect API key management infrastructure).
   * Defines `DEFAULT_HARNESS` to support cross-skill regression tests without NameError tracebacks.

3. **RAM Disk Sandbox Isolation Engine (`sandbox.py`):**
   * Executes code mutations inside isolated, resource-constrained environments.
   * Automatically mounts the `sandbox_run` directory as a `tmpfs` RAM disk (32MB) to prevent physical storage wear.
   * Implements a self-healing check that writes a dummy test file immediately after mounting, automatically falling back to normal filesystem writes if the PRoot virtual mount fails or lacks permissions.

4. **Mathematical Mutation Engine (`math_mutator.py`):**
   * AST-based constant folding, algebraic simplification, and closed-form conversions.

5. **QUBO & Quantum Classical Mutation Engine (`qubo_mutator.py`):**
   * Replaces $O(N^2)$ global quadratic updates with $O(N)$ local spin-flip delta updates, representing spins bitwise.

6. **Phase 1 / Phase 2 Scheduler (`hermit_daemon.py`):**
   * **Phase 1**: Targets untouched skills (0 merges) sorted by headroom (latency × complexity) and gates out insignificant/untestable skills to mark them as explored.
   * **Phase 2**: Uses bottleneck sort with a maximum consecutive attempts limit (3 attempts) to prevent monopolization.

7. **Global Convergence Detection & Auto-stop (`hermit_daemon.py`):**
   * Employs linear regression to track the slope of relative latency improvements in a 20-minute rolling window. Auto-stops with a `GLOBAL_PLATEAU_SHUTDOWN` event if improvement drops below 5%, or if token (5M) and runtime (2 hours) budgets are exceeded.

8. **Semantic Stability & Cycle Oscillation Banning (`orchestrator.py`):**
   * Detects repeated code mutations or rebounds (e.g. A-B-A-B sequences) and bans those strategies from prompts for 5 cycles. Prevents over-aggressive banning of successful strategies without history.

9. **Cross-Skill Regression Testing (`orchestrator.py`):**
   * Automatically extracts static call dependencies and stores them in `skill_dependencies`. Whenever a skill is optimized, it triggers sandbox regression checks on all downstream dependents.

10. **Quota-Aware API KeyPool (`orchestrator.py`):**
    * Tracks RPM (cap: 12), TPM (cap: 200k), and daily TPM (cap: 1M) for each API key in `api_keys.txt`. Swaps to the least-used viable key and penalizes rate-limited keys.

11. **Context Retention & Persistent Anti-patterns (`orchestrator.py`):**
    * Aggregates compilation/runtime exceptions into `anti_patterns` database and translates them into permanent synthesizer prompt constraints.

12. **Predictive Thermal-Aware Throttling (`hermit_daemon.py`):**
    * Monitors CPU temperature zones and calculates trend slopes to predictively adjust sleep cooldowns and sandbox parallelism, preventing thermal spikes.

13. **Scheduled Validation and Self-Patch Rollbacks (`orchestrator.py`):**
    * Records self-patch operations in `scheduled_validations` and copies versioned backups. Checks systems after 1 hour, reverting via backups if tests fail.

14. **Baseline Harness Freezing and Drift Rejection (`orchestrator.py`):**
    * Freezes verification harnesses and hashes in the database. Overrides defaults when first run occurs, and rejects subsequent drift with `HARNESS_DRIFT_ERROR`.

## Setup & Testing

1. Run the structural MCP verification test:
   ```bash
   python3 orchestrator.py --mode shadow_test
   ```
2. Run standard unit testing:
   ```bash
   python3 test_hermit.py
   ```
3. Run the math mutator unit tests:
   ```bash
   python3 test_math_mutator.py
   ```
4. Run the math integration tests:
   ```bash
   python3 test_math_integration.py
   ```
5. Run the QUBO mutator unit tests:
   ```bash
   python3 test_qubo_mutator.py
   ```
6. Run the QUBO integration tests:
   ```bash
   python3 test_qubo_integration.py
   ```
7. Run the research agent tests:
   ```bash
   python3 test_researcher.py
   ```
8. Run the key-rotation unit tests:
   ```bash
   python3 test_key_rotation.py
   ```
9. Start the background daemon:
   ```bash
   python3 hermit_daemon.py
   ```
10. Monitor evolution:
    ```bash
    python3 monitor_evolution.py
    ```
