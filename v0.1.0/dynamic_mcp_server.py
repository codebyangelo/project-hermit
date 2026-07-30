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
