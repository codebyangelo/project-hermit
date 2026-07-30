# Project Hermit v0.1.1 - Recursive Self-Improvement Architecture

Version `v0.1.1` extends the decoupled Model Context Protocol (MCP) server architecture from `v0.1.0` with specialized upgrades designed to enable fully autonomous, safe, and successful recursive self-improvement.

## Core Features

1. **Decoupled Mutable Tool Payload (`dynamic_mcp_server.py`):**
   * Acts as the dynamic mutable registry target for self-evolution.
   * Defines two entry points: `get_tool_manifest()` and `execute_tool(name, arguments)`.
   * **v0.1.1 Decoupling:** Tool computations (`read_skill_source`, `mutate_mcp_infrastructure`, `execute_sandbox_test`) are extracted into standalone helper functions. The main `execute_tool` acts as a simple lookup router, isolating side-effect boundaries and simplifying self-mutation targets.

2. **Static Host Controller (`orchestrator.py` / `StaticMCPHost`):**
   * Houses the protected, immutable engine layer.
   * Features a dynamic hot-reload system via `importlib.reload` to safely pull in mutated tool versions without interrupting the main host process.
   * Implements strict framework protection protocols by blocking tool calls to elements defined in `EXCLUDED_SKILLS`.
   * Enforces `frozenset` constant-time lookup for infrastructure security boundaries to optimize AST walk iterations.
   * **v0.1.1 AST Pre-Checks:** Enforces automatic AST syntax parse validation on all proposed code modifications and adversarial tests prior to launching the sandbox, optimizing token execution loops.

3. **Sandbox Isolation Engine (`sandbox.py`):**
   * Executes code mutations inside isolated, resource-constrained environments.
   * **v0.1.1 Typeless/Auto-Import injection:** Automatically prepends typing import headers (e.g. `from typing import List, Dict, ...`) to Python scripts to prevent common NameError exceptions on type annotations during sandboxed tests.

## Setup & Testing

1. Run the structural MCP verification test:
   ```bash
   python3 orchestrator.py --mode shadow_test
   ```
2. Run standard unit testing to verify orchestrator database registry, discovery, and self-patching integrity:
   ```bash
   python3 test_hermit.py
   ```
3. Start the background daemon:
   ```bash
   export GEMINI_API_KEY=<your_key>
   python3 hermit_daemon.py
   ```
4. Run concurrent integration tests:
   ```bash
   python3 test_integration.py
   ```
5. Monitor evolution:
   ```bash
   python3 monitor_evolution.py
   ```
