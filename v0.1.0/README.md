# Project Hermit v0.1.0 - Decoupled Model Context Protocol (MCP) Server Architecture

Version `v0.1.0` implements a decoupled Model Context Protocol (MCP) server architecture for Project Hermit. This architectural pattern isolates the core background loop orchestrator from the tool payload, allowing the system to safely execute recursive self-modification by mutating its own tool schema and execution definitions without crashing the running host process.

## Core Features

1. **Decoupled Mutable Tool Payload (`dynamic_mcp_server.py`):**
   * Acts as the dynamic mutable registry target for self-evolution.
   * Defines two entry points: `get_tool_manifest()` and `execute_tool(name, arguments)`.
   * Exposes three initial tools:
     * `read_skill_source`: Reads raw source code of active registered skills.
     * `mutate_mcp_infrastructure`: Overwrites `dynamic_mcp_server.py` with syntax-validated updates.
     * `execute_sandbox_test`: Runs localized syntax validation and integration tests inside isolated sandbox.

2. **Static Host Controller (`orchestrator.py` / `StaticMCPHost`):**
   * Houses the protected, immutable engine layer.
   * Features a dynamic hot-reload system via `importlib.reload` to safely pull in mutated tool versions without interrupting the main host process.
   * Implements strict framework protection protocols by blocking tool calls to elements defined in `EXCLUDED_SKILLS`.
   * Enforces `frozenset` constant-time lookup for infrastructure security boundaries to optimize AST walk iterations.

3. **Resilience & Testing Stubs:**
   * Includes structural JSON-RPC parsing validation and integration mode (`--mode shadow_test`).
   * Backwards compatible with the existing `Orchestrator` agent engine, database pipelines, daemon modes, and CLI chat.

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
