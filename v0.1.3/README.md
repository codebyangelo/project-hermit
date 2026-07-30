# Project Hermit v0.1.2 - Recursive Self-Improvement Architecture

Version `v0.1.2` extends the decoupled Model Context Protocol (MCP) server architecture from `v0.1.1` with two new modules that work in tandem with the evolutionary pipeline to analyze and optimize mathematical and quantum computations on classical hardware.

## Core Features

1. **Decoupled Mutable Tool Payload (`dynamic_mcp_server.py`):**
   * Acts as the dynamic mutable registry target for self-evolution.
   * Defines entry points: `get_tool_manifest()` and `execute_tool(name, arguments)`.
   * **v0.1.2 Update:** Exposes `mutate_math_in_code` and `mutate_qubo_in_code` tools as part of the MCP inventory, allowing other agents and modules to directly query AST mathematical and QUBO optimizations.

2. **Static Host Controller (`orchestrator.py` / `StaticMCPHost`):**
   * Houses the protected, immutable engine layer.
   * Features a dynamic hot-reload system via `importlib.reload` to safely pull in mutated tool versions without interrupting the main host process.
   * Implements strict framework protection protocols by blocking tool calls to elements defined in `EXCLUDED_SKILLS`.
   * **v0.1.2 Update:** Integrates the mathematical mutation engine (`math_mutator.py`) and the QUBO/quantum mutation engine (`qubo_mutator.py`) in tandem with the synthesizer variant generation step. Specialized mathematical and quantum/classical optimization variants are proposed, run inside the sandbox, and evaluated alongside Synthesizer models to determine the optimal Pareto-efficient candidate.

3. **Sandbox Isolation Engine (`sandbox.py`):**
   * Executes code mutations inside isolated, resource-constrained environments.
   * Prepend typing import headers (e.g. `from typing import List, Dict, ...`) to Python scripts to prevent common NameError exceptions on type annotations during sandboxed tests.

4. **Mathematical Mutation Engine (`math_mutator.py`):**
   * Works in tandem with the orchestrator to optimize mathematical functions.
   * Combines rule-based AST transformation (constant folding, algebraic simplification like `x**2` -> `x*x`, `x**0.5` -> `math.sqrt(x)`, multiplicative/additive identity elimination, bit shifts for power-of-two multiplication/division, and closed-form range sum conversion) and LLM-driven numerical optimization.

5. **QUBO & Quantum Classical Mutation Engine (`qubo_mutator.py`):**
   * Works in tandem with the orchestrator to optimize Quadratic Unconstrained Binary Optimization (QUBO) and quantum equations emulated on classical hardware.
   * Combines AST-based pattern matching (detecting double-loop quadratic summation structures) and LLM-driven quantum transformations (e.g. converting $O(N^2)$ global energy updates to $O(N)$ local incremental spin-flip delta updates, representing spins bitwise, and applying symmetric matrix reductions).

6. **Telemetry & Failure Correlation:**
   * Queries and appends historical mutation attempts (last 5 variants) and sandbox execution crash logs (last 3 stderr tracebacks) directly to the Synthesizer and QA Agent prompts.
   * Replaces version-based scheduling in the daemon with data-driven bottleneck ranking, prioritizing untested skills (0.0 ms average latency) first, then sorting skills by average sandbox latency descending to target the slowest components.

7. **Telemetry Observation Engine (`observer.py`):**
   * Gathers comprehensive database stats across active skills, branch optimizations, sandbox test runs, and Gemini API token counts.
   * Automatically invokes Gemini at the end of every evolution step (whether successful or failed/plateaued) to synthesize a detailed, timestamped Markdown report (`evolution_report_<timestamp>.md`) containing regression diagnoses, efficiency metrics, and future optimization targets.

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
