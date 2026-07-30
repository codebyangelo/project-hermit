```markdown
# //MISSION_CONTROL: PROJECT HERMIT v0.1.0 MCP IMPLEMENTATION DECK

[SYSTEM_DIRECTIVE]: Execute this specification exactly. Do not shift architectural patterns, do not introduce external dependencies, and do not default to truncated or lazy placeholders. Every block must be structurally functional and native to the local Termux environment.

---

## 🎯 OBJECTIVE
Implement a decoupled Model Context Protocol (MCP) server architecture for Project Hermit v0.1.0. This architectural pattern isolates the core background loop orchestrator from the tool payload, allowing the system to safely execute recursive self-modification by mutating its own tool schema and execution definitions without crashing the running host process.

---

## 📂 WORKSPACE SPECIFICATION
You are modifying and creating files within the active target directory: `/root/home/projects/project-hermit/v0.1.0/`

Create or modify these two foundational files precisely:
1. `dynamic_mcp_server.py` — The Mutable Tool Payload (The Target for Self-Evolution).
2. `orchestrator.py` — The Static Host Controller (Protected Layer - Immutable).

---

## 🛠️ FILE 1: THE MUTABLE TOOL PAYLOAD

Create `dynamic_mcp_server.py`. This file must act as the dynamic registry. The agent layer will actively rewrite, append, and remove items from this tool inventory. It must contain two unified entry points: `get_tool_manifest()` and `execute_tool(name, arguments)`.

```python
# dynamic_mcp_server.py
# ARCHITECTURAL ROLE: MUTABLE TOOL INVENTORY (SELF-EVOLUTION TARGET)
# Ensure clean string/byte operations and native execution handling.

import os
import sys
import subprocess

def get_tool_manifest():
    """
    Returns the JSON-RPC compliant tool definitions schema.
    This manifest is dynamically read by the static orchestrator host.
    """
    return {
        "tools": [
            {
                "name": "read_skill_source",
                "description": "Reads raw source code of an active registered skill from the project directory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Absolute path to the target source file."}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "mutate_mcp_infrastructure",
                "description": "Overwrites dynamic_mcp_server.py to add, delete, or optimize tools.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "updated_code": {"type": "string", "description": "The complete, verified source code for dynamic_mcp_server.py."}
                    },
                    "required": ["updated_code"]
                }
            },
            {
                "name": "execute_sandbox_test",
                "description": "Runs localized syntax validation and integration tests on target skills or server code.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "test_cmd": {"type": "string", "description": "The command string to execute inside the sandbox."}
                    },
                    "required": ["test_cmd"]
                }
            }
        ]
    }

def execute_tool(name, arguments):
    """
    Router for dynamically registered tools. Handles parameter mapping and native execution.
    Returns a dictionary indicating execution status and raw text payloads.
    """
    if name == "read_skill_source":
        target_path = arguments.get("file_path")
        if not os.path.exists(target_path):
            return {"status": "error", "content": f"Path not found: {target_path}"}
        with open(target_path, "r", encoding="utf-8") as f:
            return {"status": "success", "content": f.read()}

    elif name == "mutate_mcp_infrastructure":
        # Write payload to a temporary staging file to verify integrity before applying
        staging_path = "dynamic_mcp_server.py.tmp"
        code_payload = arguments.get("updated_code")
        
        with open(staging_path, "w", encoding="utf-8") as f:
            f.write(code_payload)
            
        # Execute basic compilation validation step
        try:
            subprocess.run(
                [sys.executable, "-m", "py_compile", staging_path],
                check=True, capture_output=True, text=True
            )
            # Compilation successful; securely swap runtime files
            os.replace(staging_path, "dynamic_mcp_server.py")
            return {"status": "success", "content": "dynamic_mcp_server.py successfully mutated and verified."}
        except subprocess.CalledProcessError as err:
            if os.path.exists(staging_path):
                os.remove(staging_path)
            return {"status": "error", "content": f"Compilation failed in mutation payload: {err.stderr}"}

    elif name == "execute_sandbox_test":
        cmd_string = arguments.get("test_cmd")
        try:
            # Enforce 30 second strict timeout bounds to prevent infinite test hangs
            res = subprocess.run(
                cmd_string, shell=True, capture_output=True, text=True, timeout=30
            )
            return {
                "status": "success",
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "content": "Sandbox execution thread reached strict timeout bounds (30s)."}

    else:
        raise ValueError(f"CRITICAL: Unregistered tool signature matching requested name: {name}")

```
## 🔒 FILE 2: THE STATIC HOST CONTROLLER
Modify orchestrator.py to strip out arbitrary file parsing mechanics and replace them with the StaticMCPHost pipeline. Enforce the frozenset optimization pattern for standard framework exclusions to optimize AST walk iterations.
```python
# orchestrator.py
# ARCHITECTURAL ROLE: STATIC HOST CONTROLLER (PROTECTED ENGINE LAYER)
# Enforces system isolation, hot-reloads modules, and routes standard JSON-RPC.

import sys
import json
import importlib
import dynamic_mcp_server

# Enforce strict constant-time lookup for infrastructure security boundaries
EXCLUDED_SKILLS = frozenset({
    "main", "run_loop", "setUp", "tearDown", "test_self_patching",
    "check_status", "list_skills", "list_branches", "show_failures",
    "monitor", "compile_report", "safe_api_call", "send_message",
    "run_analytical_chat", "__init__"
})

class StaticMCPHost:
    def __init__(self):
        self.server_module = dynamic_mcp_server
        self.db_path = "hermit_memory.db"

    def hot_reload_mcp_context(self) -> bool:
        """
        Dynamically reloads the mutable tool file into memory.
        If compilation has broken, catches the exception cleanly to prevent host crash.
        """
        try:
            importlib.reload(self.server_module)
            sys.stdout.write("//SYSTEM: dynamic_mcp_server reloaded into execution context.\n")
            return True
        except Exception as err:
            sys.stderr.write(f"//CRITICAL: Core hot-reload blocked. Rolling back. Reason: {str(err)}\n")
            return False

    def handle_mcp_request(self, raw_json_rpc):
        """
        Processes standard input payloads following JSON-RPC mechanics.
        Ensures strict containment matching 'tools/list' and 'tools/call' methods.
        """
        try:
            payload = json.loads(raw_json_rpc)
            method = payload.get("method")
            msg_id = payload.get("id", 0)
            
            if method == "tools/list":
                # Always hot-reload first to ensure the manifest includes recent self-mutations
                self.hot_reload_mcp_context()
                manifest = self.server_module.get_tool_manifest()
                return json.dumps({"jsonrpc": "2.0", "result": manifest, "id": msg_id})
                
            elif method == "tools/call":
                params = payload.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                # Check for framework protection protocol constraints
                if tool_name in EXCLUDED_SKILLS:
                    return json.dumps({
                        "jsonrpc": "2.0", 
                        "error": {"code": -32601, "message": f"Execution Blocked: {tool_name} is protected framework infrastructure."},
                        "id": msg_id
                    })
                
                # Route execution directly into the decoupled mutable module
                exec_out = self.server_module.execute_tool(tool_name, arguments)
                return json.dumps({"jsonrpc": "2.0", "result": exec_out, "id": msg_id})
                
            else:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": msg_id
                })
                
        except Exception as fatal_err:
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal host loop error: {str(fatal_err)}"},
                "id": 0
            })

if __name__ == "__main__":
    # Integration test check verification stub
    if len(sys.argv) > 1 and sys.argv[1] == "--mode":
        if sys.argv[2] == "shadow_test":
            host = StaticMCPHost()
            test_call = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
            res = host.handle_mcp_request(json.dumps(test_call))
            parsed = json.loads(res)
            if "result" in parsed and "tools" in parsed["result"]:
                sys.stdout.write("//INTEGRATION_TEST: Structural MCP verification PASSED.\n")
                sys.exit(0)
            else:
                sys.stderr.write("//INTEGRATION_TEST: FAILED. Output structurally malformed.\n")
                sys.exit(1)

```
## 📈 VERIFICATION PROTOCOL
After writing these files to disk, execute integration testing via your active runtime sandbox immediately to verify performance and structural compatibility:
```bash
python3 orchestrator.py --mode shadow_test

```
Confirm the return exit code maps to 0 and yields structural confirmation logs precisely. Ensure all internal state data points remain cleanly decoupled inside hermit_memory.db.
```

```

