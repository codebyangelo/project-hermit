# Project Hermit v0.1.7 - Recursive Self-Improvement Architecture

Version `v0.1.7` introduces queue starvation fairness scheduling, global convergence limits, API key quota management, cross-skill regression testing, and RAM disk sandbox execution.

## Core Features

1. **Decoupled Mutable Tool Payload (`dynamic_mcp_server.py`):**
   * Acts as the registry target for self-evolution, mutating tools without interrupting host execution.

2. **Static Host Controller (`orchestrator.py` / `StaticMCPHost`):**
   * Houses the protected engine layer with dynamic context hot-reloading via `importlib.reload`.
   * Enforces strict framework protection via `EXCLUDED_SKILLS` whitelist.
   * Defines `DEFAULT_HARNESS` to support cross-skill regression tests without NameError tracebacks.

3. **RAM Disk Sandbox Isolation Engine (`sandbox.py`):**
   * Executes code mutations inside isolated, resource-constrained environments.
   * Automatically mounts the `sandbox_run` directory as a `tmpfs` RAM disk (32MB) to prevent physical storage wear.
   * Implements a self-healing check that writes a dummy test file immediately after mounting, automatically falling back to normal filesystem writes if the PRoot virtual mount fails or lacks permissions.

4. **Mathematical Mutation Engine (`math_mutator.py`):**
   * AST-based constant folding, algebraic simplification, and closed-form conversions.

5. **QUBO & Quantum Classical Mutation Engine (`qubo_mutator.py`):**
   * Replaces $O(N^2)$ global quadratic updates with $O(N)$ local spin-flip delta updates, representing spins bitwise.

6. **Queue Starvation / Fairness Quota Scheduler (`hermit_daemon.py`):**
   * Uses a randomized fairness quota scheduler (70% bottleneck latency sort, 20% zero-merge untouched skills, 10% random exploration) to select optimization targets.

7. **Global Convergence Detection & Auto-stop (`hermit_daemon.py`):**
   * Employs linear regression to track the slope of relative latency improvements in a 20-minute rolling window. Auto-stops with a `GLOBAL_PLATEAU_SHUTDOWN` event if improvement drops below 5%, or if token (5M) and runtime (2 hours) budgets are exceeded.

8. **Semantic Stability & Oscillation Cycle Banning (`orchestrator.py`):**
   * Detects repeated code mutations (if same code is merged > 2 times in the last 10 attempts) and bans those strategies from prompts for 5 cycles.

9. **Cross-Skill Regression Testing (`orchestrator.py`):**
   * Automatically extracts static call dependencies and stores them in `skill_dependencies`. Whenever a skill is optimized, it triggers sandbox regression checks on all downstream dependents.

10. **Quota-Aware API KeyPool (`orchestrator.py`):**
    * Tracks RPM (cap: 12), TPM (cap: 200k), and daily TPM (cap: 1M) for each API key in `api_keys.txt`. Swaps to the least-used viable key and penalizes rate-limited keys for 60s.

11. **Context Retention & Persistent Anti-patterns (`orchestrator.py`):**
    * Aggregates compilation/runtime exceptions into `anti_patterns` database and translates them into permanent synthesizer prompt constraints.

12. **Thermal-Aware Throttling (`hermit_daemon.py`):**
    * Monitors CPU temperature zone sensors and dynamically sleeps (10s if > 55°C, 30s if > 65°C, 60s if > 75°C) to prevent overheating.
    * Automatically filters out unphysical or disabled zone readings outside $[-50^\circ\text{C}, 150^\circ\text{C}]$ to handle mock/virtual PRoot sensors.

13. **Independent Meta-Optimization Research Agent (`researcher.py`):**
    * Triggers autonomously when the daemon runs out of runnable targets to analyze failures and generate strategy directives.

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
