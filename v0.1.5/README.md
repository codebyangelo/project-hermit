# Project Hermit v0.1.5 - Recursive Self-Improvement Architecture

Version `v0.1.5` introduces a Meta-Optimization Research Engine (`researcher.py`) that independently audits sandbox tracebacks for stuck targets and injects custom strategic advice into the synthesizer, mutating how the optimizer thinks.

## Core Features

1. **Decoupled Mutable Tool Payload (`dynamic_mcp_server.py`):**
   * Acts as the dynamic mutable registry target for self-evolution.
   * Defines entry points: `get_tool_manifest()` and `execute_tool(name, arguments)`.
   * Mutates tool versions without interrupting the main host process.

2. **Static Host Controller (`orchestrator.py` / `StaticMCPHost`):**
   * Houses the protected, immutable engine layer.
   * Features a dynamic hot-reload system via `importlib.reload` to safely pull in mutated tool versions without interrupting the main host process.
   * Implements strict framework protection protocols by blocking tool calls to elements defined in `EXCLUDED_SKILLS`.
   * **v0.1.2 Update:** Integrates the mathematical mutation engine (`math_mutator.py`) and the QUBO/quantum mutation engine (`qubo_mutator.py`) in tandem with the synthesizer variant proposal step.

3. **Sandbox Isolation Engine (`sandbox.py`):**
   * Executes code mutations inside isolated, resource-constrained environments.
   * Prepends typing import headers to Python scripts to prevent common NameError exceptions on type annotations during sandboxed tests.

4. **Mathematical Mutation Engine (`math_mutator.py`):**
   * AST-based constant folding, algebraic simplification, and closed-form conversions.

5. **QUBO & Quantum Classical Mutation Engine (`qubo_mutator.py`):**
   * Replaces $O(N^2)$ global quadratic updates with $O(N)$ local spin-flip delta updates, representing spins bitwise.

6. **Telemetry & Failure Correlation:**
   * Appends historical mutations (last 5 variants) and sandbox tracebacks (last 3 crashes) directly to optimizer prompts.
   * Sorts bottlenecks prioritizing untested (0.0 ms average latency) first, then slowest components.

7. **Telemetry Observation Engine (`observer.py`):**
   * Periodically queries stats and invokes Gemini to write timestamped observation reports (`evolution_report_<timestamp>.md`).

8. **Intelligent Target Bypassing & Pivots:**
   * Tracks consecutive failed evolution steps (up to 3).
   * Applies dynamic pivot instructions (e.g. type-safety, algorithmic simplifications) on retries.
   * Categorizes plateaued skills as `COMPLEX_NEEDS_FURTHER_RESEARCH` in description, bypassing them in the daemon loop.

9. **Independent Meta-Optimization Research Agent (`researcher.py`):**
   * Triggers autonomously when the daemon runs out of runnable targets.
   * Queries recent sandbox crash logs and uses Gemini to analyze failure root causes.
   * Generates a concrete **Strategy and Architectural Directive Note** (documenting stdlib limits, edge cases, and design anti-patterns) and saves it to the `skill_research_notes` table.
   * Injects these notes directly into the Synthesizer prompt on future attempts, altering the optimizer's strategy and successfully breaking stuck optimization loops.

## Setup & Testing

1. Run the structural MCP verification test:
   ```bash
   python3 orchestrator.py --mode shadow_test
   ```
2. Run standard unit testing to verify orchestrator database registry, discovery, and self-patching integrity:
   ```bash
   python3 test_hermit.py
   ```
3. Run the math mutator unit tests:
   ```bash
   python3 test_math_mutator.py
   ```
4. Run the math integration tests checking the tandem pipeline behavior:
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
7. Start the background daemon:
   ```bash
   export GEMINI_API_KEY=<your_key>
   python3 hermit_daemon.py
   ```
8. Run concurrent integration tests:
   ```bash
   python3 test_integration.py
   ```
9. Monitor evolution:
   ```bash
   python3 monitor_evolution.py
   ```
