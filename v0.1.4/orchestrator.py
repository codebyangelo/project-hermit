import os
import sys
import json
import time
import sqlite3
import datetime
import importlib
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from sandbox import run_in_sandbox, SandboxResult
from logger import ExecutionLogger
import dynamic_mcp_server

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")
THOUGHTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thoughts.txt")

def write_thought_ledger(phase: str, component: str, details: str):
    timestamp = datetime.datetime.now().astimezone().isoformat()
    try:
        if not os.path.exists(THOUGHTS_PATH):
            with open(THOUGHTS_PATH, "w", encoding="utf-8") as f:
                f.write("=== PROJECT HERMIT: THOUGHTS LEDGER ===\n\n")
        with open(THOUGHTS_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] | {phase} | {component}\n{details}\n{'-'*80}\n")
    except Exception as e:
        pass

class Orchestrator:
    """
    Project Hermit Orchestrator v0.0.3.
    Uses Google GenAI SDK's Interactions API to manage multi-agent evolutionary mutations.
    Integrates an Adversarial QA Agent and Genetic Branching (multi-candidate variants).
    """
    # Class-level variable to enforce strict pacing between any API calls across instances
    LAST_CALL_TIME = 0.0

    EXCLUDED_SKILLS = frozenset({
        "__init__",
        "check_and_apply_context_decay",
        "check_status",
        "compile_report",
        "generate_adversarial_tests",
        "get_historical_adversarial_tests",
        "get_state_hash",
        "inject_task",
        "list_branches",
        "list_skills",
        "monitor",
        "run_analytical_chat",
        "show_failures",
        "safe_api_call",
        "send_message",
        "run_with_timer",
        "verify_and_trigger_cache",
        "safe_write_cache",
        "obfuscate_telemetry",
        "_transient_watcher",
        "_run_memmap_meta",
        "_get_playbook_path",
        "get_os_mode",
        "collect_network_connections",
        "check_rec",
        "verify_report",
        "resolve_username_from_pid",
        "find_user_in_tree",
        "main",
        "run_loop",
        "setUp",
        "tearDown",
        "test_self_patching",
        "mutate_math_in_code",
        "generate_math_mutations",
        "optimize_math_ast",
        "mutate_math_llm",
        "mutate_qubo_in_code",
        "generate_qubo_mutations",
        "optimize_qubo_ast",
        "mutate_qubo_llm"
    })

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        # Enforce gemini-3.1-flash-lite and not any other model
        self.model = "gemini-3.1-flash-lite"

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def has_api_access(self) -> bool:
        return len(self.api_key.strip()) > 0

    def get_rolling_telemetry(self) -> Tuple[int, int, int]:
        """Calculates actual rolling telemetry from the database."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # RPD
        cursor.execute("SELECT COUNT(*) FROM limit_telemetry WHERE timestamp >= datetime('now', '-1 day')")
        rpd = cursor.fetchone()[0]

        # RPM
        cursor.execute("SELECT COUNT(*) FROM limit_telemetry WHERE timestamp >= datetime('now', '-1 minute')")
        rpm = cursor.fetchone()[0]

        # TPM (Estimated via prompt + output counts)
        cursor.execute("SELECT SUM(tpm) FROM limit_telemetry WHERE timestamp >= datetime('now', '-1 minute') AND tpm IS NOT NULL")
        tpm_sum = cursor.fetchone()[0]
        tpm = tpm_sum if tpm_sum is not None else 0

        conn.close()
        return rpd, rpm, tpm

    def log_api_call(self, rpd: int, rpm: int, tpm_used: int, error_code: Optional[str], latency_ms: int, notes: str):
        """Logs the API call metrics to the limit_telemetry table."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO limit_telemetry (rpd, rpm, tpm, error_code, latency_ms, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (rpd, rpm, tpm_used, error_code, latency_ms, notes))
        conn.commit()
        conn.close()

    def call_gemini_api(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """
        Queries Gemini using the new standard google-genai Interactions API.
        Enforces a strict 5-second pacing delay to guarantee staying under the 15 RPM limit.
        Includes a 5-attempt exponential backoff retry mechanism to survive temporary network issues.
        """
        if not self.has_api_access():
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        # Log outbound API call
        write_thought_ledger("TX_OUTBOUND", f"LLM_EVALUATION ({self.model})", f"System Instruction: {system_instruction}\nPrompt:\n{prompt}")

        # Enforce strict 5.0 second pacing guard
        current_time = time.time()
        time_since_last = current_time - Orchestrator.LAST_CALL_TIME
        if time_since_last < 5.0:
            sleep_needed = 5.0 - time_since_last
            ExecutionLogger.log("LLM_CLIENT", f"Rate limit defense: Pacing API call. Sleeping for {sleep_needed:.2f}s...")
            time.sleep(sleep_needed)

        max_retries = 5
        backoff_base = 2.0

        for attempt in range(1, max_retries + 1):
            rpd_before, rpm_before, tpm_before = self.get_rolling_telemetry()
            start_time = time.perf_counter()
            try:
                # Initialize the official SDK client inside the loop to ensure clean connection state
                client = genai.Client(api_key=self.api_key)
                
                generation_config = {
                    "temperature": 0.2
                }

                # Use the new official Interactions API with direct keyword parameters
                interaction = client.interactions.create(
                    model=self.model,
                    input=prompt,
                    system_instruction=system_instruction,
                    generation_config=generation_config
                )

                # Record call time to block subsequent calls
                Orchestrator.LAST_CALL_TIME = time.time()

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                # Extract response text from interaction steps
                text_parts = []
                if hasattr(interaction, 'steps') and interaction.steps:
                    for step in interaction.steps:
                        if step.type == 'model_output' and hasattr(step, 'content') and step.content:
                            for content_item in step.content:
                                if hasattr(content_item, 'text') and content_item.text:
                                    text_parts.append(content_item.text)
                response_text = "".join(text_parts) if text_parts else ""
                
                # Simple token estimation fallback for logging
                tpm_used = (len(prompt) // 4) + (len(response_text) // 4)
                ExecutionLogger.add_tokens(len(prompt) // 4, len(response_text) // 4)
                
                notes = f"Model: {self.model} | Interactions API"
                self.log_api_call(rpd_before + 1, rpm_before + 1, tpm_used, None, latency_ms, notes)
                ExecutionLogger.log("LLM_CLIENT", f"Google Interactions API call successful. Latency: {latency_ms}ms")

                # Log inbound API response
                write_thought_ledger("RX_INBOUND", "LLM_RAW_OUTPUT", f"Success! Latency: {latency_ms}ms | Est. Tokens: {tpm_used}\nResponse:\n{response_text}")

                return {
                    "success": True,
                    "text": response_text,
                    "tokens": tpm_used,
                    "latency_ms": latency_ms
                }
            except Exception as e:
                # Record call time on failure too to throttle retry storms
                Orchestrator.LAST_CALL_TIME = time.time()
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                error_code = "Exception"
                self.log_api_call(rpd_before + 1, rpm_before + 1, 0, error_code, latency_ms, f"Exception: {str(e)}")
                ExecutionLogger.log("LLM_CLIENT", f"Interactions API call exception (Attempt {attempt}/{max_retries}): {str(e)}", "ERROR")

                if attempt < max_retries:
                    sleep_time = backoff_base ** attempt
                    ExecutionLogger.log("LLM_CLIENT", f"Retrying API call in {sleep_time:.2f}s due to error: {str(e)}", "WARN")
                    time.sleep(sleep_time)
                else:
                    # Log API error on final failure
                    write_thought_ledger("RX_INBOUND", "LLM_ERROR", f"Failed all {max_retries} attempts! Last latency: {latency_ms}ms\nError: {str(e)}")
                    return {
                        "success": False,
                        "text": "",
                        "tokens": 0,
                        "latency_ms": latency_ms,
                        "error": f"Failed after {max_retries} attempts: {str(e)}"
                    }

    def register_or_update_skill(self, skill_name: str, description: str, code: str) -> bool:
        """Saves or updates a skill in the active_skills registry table."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        
        if row:
            version = row[0] + 1
            cursor.execute("""
                UPDATE active_skills 
                SET description = ?, code = ?, version = ?, timestamp = CURRENT_TIMESTAMP
                WHERE skill_name = ?
            """, (description, code, version, skill_name))
            action = "updated"
        else:
            version = 1
            cursor.execute("""
                INSERT INTO active_skills (skill_name, description, code, version)
                VALUES (?, ?, ?, 1)
            """, (skill_name, description, code))
            action = "registered"
            
        conn.commit()
        conn.close()
        ExecutionLogger.log("REGISTRY", f"Skill '{skill_name}' successfully {action} (Version {version}).", "SUCCESS")
        return True

    def patch_source_file_with_skill(self, skill_name: str, optimized_code: str) -> bool:
        """
        Introspection self-patch: If the optimized skill is part of Project Hermit's own source code,
        replace its definition in the local source file, run unit tests to verify integrity,
        and commit or roll back depending on the result.
        """
        import ast
        import shutil
        import subprocess
        
        self_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Scan python files in Project Hermit's directory
        target_file = None
        target_node = None
        
        for root, _, files in os.walk(self_dir):
            if "sandbox_run" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py") and file != "test_hermit.py" and file != "test_integration.py":
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef) and node.name == skill_name:
                                target_file = file_path
                                target_node = node
                                break
                        if target_file:
                            break
                    except Exception:
                        pass
            if target_file:
                break
                
        if not target_file or not target_node:
            # The skill doesn't belong to project-hermit's codebase (it might belong to lobster or mantis)
            return False
            
        ExecutionLogger.log("INTROSPECTION", f"Found self-matching function '{skill_name}' in source file: {os.path.relpath(target_file, self_dir)}")
        write_thought_ledger("INTROSPECTION_SELF_PATCH", f"Initiating self-patch for '{skill_name}'", f"Target file: {target_file}")
        
        # Create backup
        backup_path = target_file + ".bak"
        try:
            shutil.copy2(target_file, backup_path)
            
            with open(target_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            # Replace lines of the function definition
            start_idx = target_node.lineno - 1
            end_idx = getattr(target_node, 'end_lineno', start_idx + 1)
            
            # Replace slice with optimized code (ensure it ends with newline)
            new_lines_str = optimized_code if optimized_code.endswith("\n") else optimized_code + "\n"
            lines[start_idx:end_idx] = [new_lines_str]
            
            with open(target_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            ExecutionLogger.log("INTROSPECTION", "Code injected. Running unit tests to verify system integrity...")
            
            # Run unit tests to verify
            test_res = subprocess.run(
                [sys.executable, "test_hermit.py"],
                capture_output=True,
                text=True,
                cwd=self_dir
            )
            
            if test_res.returncode == 0:
                ExecutionLogger.log("INTROSPECTION", "INTEGRITY CHECK SUCCESSFUL: Unit tests passed. Self-patch committed!", "SUCCESS")
                write_thought_ledger("INTROSPECTION_PATCH_COMMIT", f"Self-patch committed for '{skill_name}'", f"Verified successfully by running test_hermit.py.\nStdout:\n{test_res.stdout}")
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                return True
            else:
                ExecutionLogger.log("INTROSPECTION", "INTEGRITY CHECK FAILED: Unit tests failed. Rolling back self-patch...", "ERROR")
                write_thought_ledger("INTROSPECTION_PATCH_ROLLBACK", f"Self-patch rolled back for '{skill_name}'", f"Integrity check failed.\nExit code: {test_res.returncode}\nStderr:\n{test_res.stderr}\nStdout:\n{test_res.stdout}")
                # Restore backup
                shutil.move(backup_path, target_file)
                return False
                
        except Exception as e:
            ExecutionLogger.log("INTROSPECTION", f"Self-patch error occurred: {e}. Restoring backup if exists...", "ERROR")
            if os.path.exists(backup_path):
                shutil.move(backup_path, target_file)
            return False

    def get_skill(self, skill_name: str) -> Optional[Tuple[str, str, int]]:
        """Retrieves a skill from the database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT description, code, version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_skill_history(self, skill_name: str) -> List[Dict[str, Any]]:
        """Retrieves history of proposed variants for a skill to feed context."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT branch_name, latency_ms, max_rss_kb, complexity_score, status 
                FROM skill_branches 
                WHERE skill_name = ? 
                ORDER BY id DESC LIMIT 5
            """, (skill_name,))
            rows = cursor.fetchall()
            return [
                {
                    "branch_name": r[0],
                    "latency_ms": r[1],
                    "max_rss_kb": r[2],
                    "complexity": r[3],
                    "status": r[4]
                }
                for r in rows
            ]
        except Exception:
            return []
        finally:
            conn.close()

    def get_recent_failures(self, skill_name: str) -> List[Dict[str, Any]]:
        """Retrieves recent sandbox failures for a skill to avoid regression."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT script_name, stderr, timestamp 
                FROM reality_tests 
                WHERE script_name LIKE ? AND status = 'FAIL'
                ORDER BY id DESC LIMIT 3
            """, (f"%{skill_name}%",))
            rows = cursor.fetchall()
            return [
                {
                    "script_name": r[0],
                    "stderr": r[1],
                    "timestamp": r[2]
                }
                for r in rows
            ]
        except Exception:
            return []
        finally:
            conn.close()

    def get_all_skills(self) -> List[Tuple[str, str, int]]:
        """Retrieves all registered skills from the database, excluding framework infrastructure."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name, description, version FROM active_skills")
        rows = cursor.fetchall()
        conn.close()
        return [row for row in rows if row[0] not in self.EXCLUDED_SKILLS]

    def save_branch_variant(self, skill_name: str, branch_name: str, code: str, latency: float, rss: int, complexity: int, status: str):
        """Saves a candidate branch variant to the database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO skill_branches (skill_name, branch_name, code, latency_ms, max_rss_kb, complexity_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (skill_name, branch_name, code, latency, rss, complexity, status))
        conn.commit()
        conn.close()

    def save_adversarial_test(self, skill_name: str, test_code: str):
        """Saves an adversarial test checking routine to prevent regression."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO adversarial_tests (skill_name, test_code)
            VALUES (?, ?)
        """, (skill_name, test_code))
        conn.commit()
        conn.close()

    def get_historical_adversarial_tests(self, skill_name: str) -> List[str]:
        """Loads all past generated adversarial tests to prevent regression checks."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT test_code FROM adversarial_tests WHERE skill_name = ?", (skill_name,))
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]

    def generate_adversarial_tests(self, skill_name: str, desc: str, baseline_code: str) -> str:
        """
        Uses the QA Tester Agent via Interactions API to dynamically write assert checks
        specifically designed to break/stress-test mutations.
        """
        ExecutionLogger.log("QA_AGENT", f"QA Agent generating adversarial tests for '{skill_name}'...")
        
        system_instruction = (
            "You are Project Hermit's Adversarial QA Auditor.\n"
            "Your task is to write automated boundary and edge-case Python tests (using asserts) to stress-test optimized code mutations.\n"
            "You must return your output ONLY as a valid JSON object matching the requested schema. No prose, no markdown formatting."
        )

        prompt = f"""
        Create an adversarial test harness for the Python function '{skill_name}'.
        
        FUNCTION DESCRIPTION:
        {desc}
        
        BASELINE CODE UNDER AUDIT:
        ```python
        {baseline_code}
        ```
        
        INSTRUCTIONS:
        1. Write 3-5 aggressive test assertions that target empty inputs, boundary cases, mismatching inputs, or overflow conditions.
        2. Write ONLY the test assertions and setup variables. Do NOT define or redefine the function '{skill_name}' under audit, as it is already defined and provided by the testing environment. Your code must directly call '{skill_name}(...)'.
        3. Do not import third-party packages. Only use Python's built-in standard library.
        4. Return a valid JSON matching this schema:
        {{
            "adversarial_test_code": "The complete Python test assertions and setup variables."
        }}
        """

        res = self.call_gemini_api(prompt, system_instruction)
        if not res["success"]:
            raise RuntimeError(f"QA Agent API Call failed: {res['error']}")

        try:
            clean_text = res["text"].strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            qa_json = json.loads(clean_text)
            test_code = qa_json["adversarial_test_code"]
            
            import re
            pattern_def = rf"def\s+{skill_name}\s*\(.*?\)(?:\s*->\s*.*?)?\s*:\n(?:[ \t]+.*\n?)*"
            test_code_clean = re.sub(pattern_def, "", test_code)
            
            ExecutionLogger.log("QA_AGENT", "Successfully generated adversarial test assertions.", "SUCCESS")
            return test_code_clean
        except Exception as e:
            raise RuntimeError(f"QA Agent failed to parse test JSON: {e}. Raw: {res['text']}")

    def discover_and_register_new_skill(self) -> Tuple[bool, str]:
        """
        Scans the workspace codebases (including project-hermit itself for introspection,
        project-lobster, and project-mantis), extracts computational functions using AST,
        prompts the Discovery Agent to select the most relevant bottleneck skill,
        constructs a baseline and a verification harness, and registers it.
        """
        ExecutionLogger.log("DISCOVERY", "Starting autonomous skill discovery...")
        import ast

        # Query already registered skills to avoid re-discovering and resetting them
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name FROM active_skills")
        registered_skills = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        self_dir = os.path.dirname(os.path.abspath(__file__))
        active_version_name = os.path.basename(self_dir)
        workspace_root = "/root/home/projects"
        
        # Prioritize self-introspection first, then lobster and mantis
        prioritized_dirs = [
            self_dir,
            os.path.join(workspace_root, "project-lobster/src"),
            os.path.join(workspace_root, "project-mantis/agent_v0.5.5")
        ]
        
        # Fallback to the whole workspace if prioritized dirs don't exist
        search_dirs = [d for d in prioritized_dirs if os.path.exists(d)]
        if not search_dirs:
            search_dirs = [workspace_root]
            
        candidates = []
        for sdir in search_dirs:
            for root, dirs, files in os.walk(sdir):
                # Skip hidden and pycache
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                
                # Introspection version guard: if inside project-hermit, skip inactive versions
                if "project-hermit" in root:
                    dirs[:] = [d for d in dirs if d == active_version_name]
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                source_code = f.read()
                            lines = source_code.splitlines()
                            tree = ast.parse(source_code)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef):
                                    if node.name in registered_skills:
                                        continue
                                    if node.name in self.EXCLUDED_SKILLS:
                                        continue
                                    # Heuristic logic for computational bottleneck candidates
                                    length = getattr(node, 'end_lineno', len(lines)) - node.lineno + 1
                                    # Limit function line length to keep the scope appropriate (5 to 80 lines)
                                    if not (5 <= length <= 80):
                                        continue
                                    
                                    has_loop = False
                                    has_string_op = False
                                    for child in ast.walk(node):
                                        if isinstance(child, (ast.For, ast.While, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                                            has_loop = True
                                        if isinstance(child, ast.Call):
                                            if isinstance(child.func, ast.Attribute):
                                                if child.func.attr in ('split', 'strip', 'join', 'replace', 'encode', 'decode', 'search', 'match', 'find', 'findall', 'hexdump'):
                                                    has_string_op = True
                                    
                                    name_lower = node.name.lower()
                                    if any(k in name_lower for k in ('search', 'parse', 'carve', 'extract', 'decode', 'hexdump', 'sieve', 'score', 'match', 'check')):
                                        has_string_op = True
                                        
                                    if has_loop or has_string_op:
                                        func_code = "\n".join(lines[node.lineno-1 : getattr(node, 'end_lineno', len(lines))])
                                        candidates.append({
                                            "file": os.path.relpath(file_path, workspace_root),
                                            "name": node.name,
                                            "code": func_code,
                                            "length": length
                                        })
                        except Exception:
                            pass
                            
        if not candidates:
            # Fallback if no candidate is found
            err_msg = "No computational functions found in the workspace."
            ExecutionLogger.log("DISCOVERY", err_msg, "WARN")
            return False, err_msg
            
        # Limit to 15 candidates to avoid token blowup
        candidates = candidates[:15]
        
        # Build compact listing for LLM
        candidates_str = ""
        for idx, cand in enumerate(candidates):
            candidates_str += f"\n--- Candidate #{idx+1} ---\n"
            candidates_str += f"File: {cand['file']}\n"
            candidates_str += f"Function Name: {cand['name']}\n"
            candidates_str += f"Code:\n```python\n{cand['code']}\n```\n"
            
        system_instruction = (
            "You are Project Hermit's Autonomous Skill Discovery Agent.\n"
            "Your task is to analyze candidate functions in the workspace, select the most suitable bottleneck function for optimization (e.g. text/byte search, parsing, loop-heavy math), and output its details alongside a high-pressure verification harness.\n"
            "You must return your output ONLY as a valid JSON object matching the requested schema. No prose, no markdown formatting."
        )
        
        prompt = f"""
        Analyze these python functions extracted from the workspace. Choose ONE function that is a prime candidate for performance optimization (e.g., custom byte carving, heuristic scans, parsing loops).
        
        CRITICAL CONSTRAINT:
        Do NOT select any function that is already registered as a skill in our database.
        The list of already registered skills to avoid is: {list(registered_skills)}.
        You MUST select a function that is NOT in this list.
        
        CANDIDATES FOR DISCOVERY:
        {candidates_str}
        
        INSTRUCTIONS:
        1. Select the single best function to optimize.
           CRITICAL: Prioritize functions that are standard, self-contained algorithms or utility functions (such as parsing, byte scanning, string decoding, hex dump, or network port parsing).
           DO NOT select complex class methods that depend heavily on external frameworks or databases (such as volatility plugins, task structures, or database interfaces) as they cannot be validated or evolved in an isolated sandbox.
        2. Provide a descriptive summary of what it does and why it is a bottleneck.
        3. Write the exact baseline code of the function. Ensure that any standard library imports needed by the function (e.g. `import re`, `import struct`, `import socket`) are included at the very top of `baseline_code`.
        4. Design a rigorous verification harness (checking inputs, edge cases, correct outputs, and printing/asserting verification success) that executes the chosen function.
        5. Return a valid JSON matching this schema:
        {{
            "selected_file": "relative file path",
            "skill_name": "the function name exactly as defined in the code",
            "description": "Descriptive summary detailing function logic and optimization opportunity.",
            "baseline_code": "The complete Python function definition along with any required standard library imports at the top.",
            "verification_harness": "Python code that sets up mock test data, runs the function, asserts the returned values are correct, and prints a success message. Do NOT define the function under test inside this verification harness, only call it."
        }}
        """
        
        ExecutionLogger.log("DISCOVERY", f"Submitting {len(candidates)} candidate functions to Gemini for autonomous selection...")
        res = self.call_gemini_api(prompt, system_instruction)
        if not res["success"]:
            err_msg = f"Discovery API call failed: {res['error']}"
            ExecutionLogger.log("DISCOVERY", err_msg, "ERROR")
            return False, err_msg
            
        try:
            clean_text = res["text"].strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            disc_json = json.loads(clean_text)
            skill_name = disc_json["skill_name"].strip()
            description = disc_json["description"].strip()
            baseline_code = disc_json["baseline_code"].strip()
            harness = disc_json["verification_harness"].strip()
            
            if skill_name in registered_skills:
                err_msg = f"Rejected re-discovery of already registered skill: '{skill_name}'"
                ExecutionLogger.log("DISCOVERY", err_msg, "WARN")
                write_thought_ledger("DISCOVERY_REJECTED", f"Skipped registering duplicate skill: {skill_name}", f"The Discovery Agent selected '{skill_name}', which is already in registered_skills: {list(registered_skills)}.")
                return False, err_msg

            # Combine verification harness inside the description using the delimiter
            db_description = f"{description}\n\n=== HARNESS ===\n{harness}"
            
            # Register the new skill
            self.register_or_update_skill(skill_name, db_description, baseline_code)
            
            # Log discovery thoughts
            discovery_details = (
                f"Selected File: {disc_json['selected_file']}\n"
                f"Selected Skill Name: {skill_name}\n"
                f"Description: {description}\n"
                f"Baseline Code:\n{baseline_code}\n"
                f"Verification Harness:\n{harness}"
            )
            write_thought_ledger("DISCOVERY_DECISION", f"Skill discovered: {skill_name}", discovery_details)

            ExecutionLogger.log("DISCOVERY", f"Successfully discovered and registered new skill '{skill_name}' from {disc_json['selected_file']}.", "SUCCESS")
            return True, skill_name
        except Exception as e:
            err_msg = f"Failed to parse or register discovered skill JSON: {e}. Raw: {res['text']}"
            ExecutionLogger.log("DISCOVERY", err_msg, "ERROR")
            write_thought_ledger("DISCOVERY_FAILED", "Parsing error", f"Exception: {str(e)}\nRaw JSON response:\n{res['text']}")
            return False, err_msg

    def run_evolution_step(self, skill_name: str, verification_harness: str, user_instruction: Optional[str] = None) -> Tuple[bool, str]:
        """
        Hermit v0.0.3 Multi-Agent Evolutionary Pipeline:
        1. Executes baseline skill against verification harness in sandbox.
        2. Invokes Synthesizer Agent to generate three distinct optimized branch candidates.
        3. Invokes QA Agent to generate adversarial test assertions based on baseline behavior.
        4. Executes all candidate mutations against BOTH test harnesses in the sandbox.
        5. Computes multi-objective scores (Latency, Memory, Code Complexity).
        6. Selects the overall Pareto-dominant mutation and registers it.
        """
        skill_info = self.get_skill(skill_name)
        if not skill_info:
            err = f"Skill '{skill_name}' is not registered."
            ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
            write_thought_ledger("EVOLUTION_FAILED", "Initialization error", f"Skill '{skill_name}' is not registered in active_skills.")
            return False, err

        desc, base_code, version = skill_info
        ExecutionLogger.log("ORCHESTRATOR", f"Initializing Evolutionary Pipeline for: {skill_name} (v{version})")

        # 1. Run baseline in sandbox
        baseline_script = f"{base_code}\n\n{verification_harness}"
        baseline_result = run_in_sandbox(baseline_script, "baseline_verify.py")
        baseline_result.log_to_db(self.db_path)

        if baseline_result.exit_code != 0:
            err = f"Baseline failed verification! Stderr: {baseline_result.stderr}"
            ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
            write_thought_ledger("EVOLUTION_FAILED", "Baseline verification failure", f"Baseline script failed verification in sandbox.\nExit Code: {baseline_result.exit_code}\nStderr:\n{baseline_result.stderr}")
            return False, err

        baseline_complexity = len(base_code)
        ExecutionLogger.log("ORCHESTRATOR", f"Baseline performance: Latency = {baseline_result.duration_ms:.2f} ms | RAM = {baseline_result.max_rss_kb} KB | Complexity = {baseline_complexity} chars", "SUCCESS")

        # Log baseline info to thoughts ledger
        baseline_details = (
            f"Skill: {skill_name}\n"
            f"Version: {version}\n"
            f"Description: {desc}\n"
            f"Baseline Latency: {baseline_result.duration_ms:.2f} ms\n"
            f"Baseline Max RSS: {baseline_result.max_rss_kb} KB\n"
            f"Baseline Complexity: {baseline_complexity} chars\n"
            f"Baseline Code:\n{base_code}"
        )
        write_thought_ledger("EVOLUTION_START", f"Evolution pipeline initialized for '{skill_name}' (v{version})", baseline_details)

        if not self.has_api_access():
            err = "No GEMINI_API_KEY detected. Aborting evolution."
            ExecutionLogger.log("ORCHESTRATOR", err, "WARN")
            write_thought_ledger("EVOLUTION_ABORTED", "No API Key", err)
            return False, err

        # 2. Query QA Agent to generate adversarial assertions and verify them against baseline
        try:
            max_retries = 3
            verified_test_code = None
            for attempt in range(1, max_retries + 1):
                adversarial_test_code = self.generate_adversarial_tests(skill_name, desc, base_code)
                
                # Verify that the baseline code passes the generated adversarial checks
                validation_script = f"{base_code}\n\n{adversarial_test_code}"
                try:
                    import ast
                    ast.parse(validation_script)
                except SyntaxError as err:
                    ExecutionLogger.log("QA_AGENT", f"Adversarial QA checks failed AST parse check on attempt {attempt}: {err}", "WARN")
                    continue
                validation_result = run_in_sandbox(validation_script, "baseline_self_verify.py")
                
                if validation_result.exit_code == 0:
                    ExecutionLogger.log("QA_AGENT", f"Adversarial QA checks successfully verified against baseline on attempt {attempt}.", "SUCCESS")
                    verified_test_code = adversarial_test_code
                    
                    # Log verified adversarial tests to the ledger
                    qa_details = (
                        f"Skill: {skill_name}\n"
                        f"Attempt: {attempt}\n"
                        f"Generated Adversarial Test Code:\n{verified_test_code}"
                    )
                    write_thought_ledger("ADVERSARIAL_QA_VERIFIED", f"Adversarial QA test verified for '{skill_name}'", qa_details)
                    break
                else:
                    ExecutionLogger.log("QA_AGENT", f"Discarded hallucinated QA test on attempt {attempt}: Failed baseline validation. Stderr: {validation_result.stderr}", "WARN")
                    write_thought_ledger("ADVERSARIAL_QA_REJECTED", f"Discarded hallucinated QA test on attempt {attempt}", f"Failed baseline validation.\nExit Code: {validation_result.exit_code}\nStderr:\n{validation_result.stderr}\nCode:\n{adversarial_test_code}")
            
            if verified_test_code is None:
                err = "Adversarial QA generation failed: QA Agent repeatedly generated hallucinated assertions that the baseline itself fails."
                ExecutionLogger.log("QA_AGENT", err, "ERROR")
                write_thought_ledger("EVOLUTION_FAILED", "QA Generation Exhausted", err)
                return False, err
                
            # Save it to history database to prevent future regressions!
            self.save_adversarial_test(skill_name, verified_test_code)
        except Exception as e:
            err = f"Adversarial QA generation failed: {e}"
            ExecutionLogger.log("QA_AGENT", err, "ERROR")
            write_thought_ledger("EVOLUTION_FAILED", "QA Exception", err)
            return False, err

        # 3. Query Synthesizer Agent to generate three distinct branch variants
        system_instruction = (
            "You are Project Hermit's Evolutionary Synthesizer Agent.\n"
            "Your task is to generate three distinct Python code mutation variants to optimize the skill code.\n"
            "You must return your output ONLY as a valid JSON object matching the requested schema."
        )

        user_instruction_str = ""
        if user_instruction:
            user_instruction_str = f"\nUSER INSTRUCTION / OPTIMIZATION CONSTRAINT:\n{user_instruction}\n"

        # Retrieve correlation and telemetry history for this skill
        history = self.get_skill_history(skill_name)
        failures = self.get_recent_failures(skill_name)
        
        history_str = ""
        if history:
            history_str += "\nHISTORICAL MUTATION ATTEMPTS (CORRELATION DATA):\n"
            for h in history:
                history_str += f"- Variant '{h['branch_name']}': Status={h['status']}, Latency={h['latency_ms']:.2f}ms, RAM={h['max_rss_kb']}KB\n"
                
        failures_str = ""
        if failures:
            failures_str += "\nRECENT COMPILATION/EXECUTION CRASHES TO AVOID:\n"
            for f in failures:
                err_lines = f['stderr'].split('\n') if f['stderr'] else []
                err_snippet = "\n  ".join(err_lines[-3:]) if err_lines else "Unknown error"
                failures_str += f"- Script '{f['script_name']}':\n  Errors:\n  {err_snippet}\n"

        prompt = f"""
        Generate three distinct optimization variants for the Python skill named '{skill_name}'.
        {user_instruction_str}
        DESCRIPTION:
        {desc}

        BASELINE CODE:
        ```python
        {base_code}
        ```

        VERIFICATION HARNESS:
        ```python
        {verification_harness}
        ```

        BASELINE METRICS:
        - Latency: {baseline_result.duration_ms:.2f} ms
        - Memory: {baseline_result.max_rss_kb} KB
        {history_str}
        {failures_str}

        INSTRUCTIONS:
        1. Propose exactly 3 distinct variants (e.g., regex loops, slicing methods, native operations).
        2. Ensure they pass the VERIFICATION HARNESS and optimize speed and RAM.
        3. Do NOT import third-party packages. Only use Python standard libraries.
        4. Return response matching this JSON schema:
        {{
            "thought": "Explain your mutation designs.",
            "variants": [
                {{
                    "branch_name": "Variant branch identification name (lowercase, underscore)",
                    "rationale": "Why this specific optimization works.",
                    "code": "The complete modified Python function definition code block."
                }}
            ]
        }}
        """

        ExecutionLogger.log("ORCHESTRATOR", "Synthesizer Agent proposing branch variants...")
        res = self.call_gemini_api(prompt, system_instruction)
        if not res["success"]:
            write_thought_ledger("EVOLUTION_FAILED", "Synthesizer API Error", res["error"])
            return False, f"Synthesizer API Error: {res['error']}"

        try:
            clean_text = res["text"].strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            synth_json = json.loads(clean_text)
            variants = synth_json["variants"]
            
            # Log proposed variants
            variants_details = ""
            for idx, var in enumerate(variants):
                variants_details += (
                    f"Variant #{idx+1}: {var['branch_name']}\n"
                    f"Rationale: {var['rationale']}\n"
                    f"Code:\n{var['code']}\n\n"
                )
            write_thought_ledger("SYNTHESIZER_MUTATIONS", f"Proposed {len(variants)} optimization variants", variants_details)
        except Exception as e:
            err = f"Failed to parse variants JSON: {e}"
            ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
            write_thought_ledger("EVOLUTION_FAILED", "Parsing Synth JSON Error", f"Exception: {str(e)}\nRaw Response:\n{res['text']}")
            return False, err

        # Generate mathematical mutation variants using the math_mutator module
        try:
            import math_mutator
            math_variants = math_mutator.generate_math_mutations(base_code, self)
            if math_variants:
                ExecutionLogger.log("ORCHESTRATOR", f"Math mutator generated {len(math_variants)} mathematical variants.", "SUCCESS")
                variants.extend(math_variants)
                
                math_details = ""
                for idx, var in enumerate(math_variants):
                    math_details += (
                        f"Math Variant #{idx+1}: {var['branch_name']}\n"
                        f"Rationale: {var['rationale']}\n"
                        f"Code:\n{var['code']}\n\n"
                    )
                write_thought_ledger("MATH_MUTATOR_MUTATIONS", f"Injected {len(math_variants)} mathematical variants", math_details)
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to run math mutator: {e}", "WARN")

        # Generate QUBO/Quantum mutation variants using the qubo_mutator module
        try:
            import qubo_mutator
            qubo_variants = qubo_mutator.generate_qubo_mutations(base_code, self)
            if qubo_variants:
                ExecutionLogger.log("ORCHESTRATOR", f"QUBO mutator generated {len(qubo_variants)} QUBO/quantum variants.", "SUCCESS")
                variants.extend(qubo_variants)
                
                qubo_details = ""
                for idx, var in enumerate(qubo_variants):
                    qubo_details += (
                        f"QUBO Variant #{idx+1}: {var['branch_name']}\n"
                        f"Rationale: {var['rationale']}\n"
                        f"Code:\n{var['code']}\n\n"
                    )
                write_thought_ledger("QUBO_MUTATOR_MUTATIONS", f"Injected {len(qubo_variants)} QUBO/quantum variants", qubo_details)
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to run QUBO mutator: {e}", "WARN")

        # Load all historical adversarial tests to prevent regression
        historical_tests = self.get_historical_adversarial_tests(skill_name)

        # 4. Evaluate each candidate against BOTH harnesses (Verification + Cumulative Adversarial)
        valid_candidates = []
        
        # Add baseline as comparison index 0
        baseline_score = (baseline_result.duration_ms * 1.0) + (baseline_result.max_rss_kb * 0.1) + (baseline_complexity * 0.05)
        ExecutionLogger.log("ORCHESTRATOR", f"Evaluating {len(variants)} generated branch mutations...")

        for var in variants:
            branch_name = var["branch_name"]
            code = var["code"]
            rationale = var["rationale"]
            
            ExecutionLogger.log("ORCHESTRATOR", f"Testing branch variant '{branch_name}': {rationale}")
            
            # Combine optimized code + verification harness + current + all historical adversarial checks
            full_test_script = f"{code}\n\n{verification_harness}"
            for idx, hist_code in enumerate(historical_tests):
                full_test_script += f"\n\n# --- Historical Test Case {idx+1} ---\n{hist_code}"

            # AST Pre-check
            try:
                import ast
                ast.parse(full_test_script)
            except SyntaxError as err:
                ExecutionLogger.log("ORCHESTRATOR", f"Branch '{branch_name}' failed AST parse check: {err}", "ERROR")
                continue

            # Run in sandbox
            result = run_in_sandbox(full_test_script, f"{branch_name}_verify.py")
            result.log_to_db(self.db_path)
            
            complexity = len(code)
            is_improved = False
            score = 0.0
            
            if result.exit_code == 0:
                # Multi-Objective score: weight speed, memory, and complexity (lower is better)
                score = (result.duration_ms * 1.0) + (result.max_rss_kb * 0.1) + (complexity * 0.05)
                
                # Check for Pareto optimization improvement
                is_improved = (
                    result.duration_ms < baseline_result.duration_ms or
                    result.max_rss_kb < baseline_result.max_rss_kb or
                    complexity < baseline_complexity
                )
                
                if is_improved:
                    valid_candidates.append({
                        "branch_name": branch_name,
                        "code": code,
                        "latency": result.duration_ms,
                        "rss": result.max_rss_kb,
                        "complexity": complexity,
                        "score": score
                    })
                    self.save_branch_variant(skill_name, branch_name, code, result.duration_ms, result.max_rss_kb, complexity, "candidate")
                    ExecutionLogger.log("ORCHESTRATOR", f"Branch '{branch_name}' PASSED all tests and is Pareto-efficient.", "SUCCESS")
                else:
                    self.save_branch_variant(skill_name, branch_name, code, result.duration_ms, result.max_rss_kb, complexity, "rejected")
                    ExecutionLogger.log("ORCHESTRATOR", f"Branch '{branch_name}' PASSED but failed to optimize metrics.", "WARN")
            else:
                self.save_branch_variant(skill_name, branch_name, code, 0.0, 0, complexity, "rejected")
                ExecutionLogger.log("QA_AGENT", f"Branch '{branch_name}' REJECTED: Failed adversarial QA tests. Stderr: {result.stderr}", "ERROR")

            # Log evaluation details to thoughts ledger
            eval_details = (
                f"Branch: {branch_name}\n"
                f"Exit Code: {result.exit_code}\n"
                f"Latency: {result.duration_ms:.2f} ms\n"
                f"Max RSS: {result.max_rss_kb} KB\n"
                f"Complexity: {complexity} chars\n"
                f"Score: {score if result.exit_code == 0 else 'N/A'}\n"
                f"Is Improved: {is_improved if result.exit_code == 0 else 'N/A'}\n"
                f"Stderr:\n{result.stderr}\n"
                f"Stdout:\n{result.stdout}"
            )
            write_thought_ledger("VARIANT_EVALUATION", f"Evaluated variant '{branch_name}'", eval_details)

        # 5. Select the best branch and merge
        if not valid_candidates:
            msg = "INTEGRATION REJECTED: No variants passed all adversarial tests and optimized metrics."
            ExecutionLogger.log("ORCHESTRATOR", msg, "WARN")
            write_thought_ledger("EVOLUTION_REJECTED", "No Pareto-optimal mutations found", msg)
            
            # Generate automated evolution observation report
            try:
                from observer import EvolutionObserver
                obs = EvolutionObserver(db_path=self.db_path)
                obs.generate_report()
            except Exception as obs_err:
                ExecutionLogger.log("ORCHESTRATOR", f"Failed to generate auto-observation report: {obs_err}", "WARN")

            return False, msg

        # Sort by composite score (lowest score wins)
        valid_candidates.sort(key=lambda x: x["score"])
        best = valid_candidates[0]
        
        # Merge best branch
        self.register_or_update_skill(skill_name, desc, best["code"])
        
        # Update branch status in database
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE skill_branches SET status = 'merged' WHERE branch_name = ? AND skill_name = ?", (best["branch_name"], skill_name))
        conn.commit()
        conn.close()
        
        # Trigger dynamic self-patching introspection
        self.patch_source_file_with_skill(skill_name, best["code"])
        
        msg = f"INTEGRATION SUCCESS: Merged branch '{best['branch_name']}' (Latency: {best['latency']:.2f}ms, RAM: {best['rss']}KB, Score: {best['score']:.2f})"
        ExecutionLogger.log("ORCHESTRATOR", msg, "SUCCESS")

        merge_details = (
            f"Merged Branch: {best['branch_name']}\n"
            f"Latency: {best['latency']:.2f} ms\n"
            f"Max RSS: {best['rss']} KB\n"
            f"Complexity: {best['complexity']} chars\n"
            f"Composite Score: {best['score']:.2f}\n"
            f"Code:\n{best['code']}"
        )
        write_thought_ledger("EVOLUTION_MERGE", f"Successfully evolved and merged branch '{best['branch_name']}'", merge_details)

        # Generate automated evolution observation report
        try:
            from observer import EvolutionObserver
            obs = EvolutionObserver(db_path=self.db_path)
            obs.generate_report()
        except Exception as obs_err:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to generate auto-observation report: {obs_err}", "WARN")

        return True, msg

def main():
    ExecutionLogger.log("ORCHESTRATOR", "[ PROJECT HERMIT - Multi-Agent Evolution Engine v0.0.3 ]", "SUCCESS")
    orchestrator = Orchestrator()

    slow_search_code = """
def hex_search(data_bytes: bytes, pattern: bytes) -> list:
    results = []
    for i in range(len(data_bytes) - len(pattern) + 1):
        match = True
        for j in range(len(pattern)):
            if data_bytes[i + j] != pattern[j]:
                match = False
                break
        if match:
            results.append(i)
    return results
"""
    harness_code = """
import time
data = b"B" * 500000 + b"FOUND_ME" + b"B" * 500000 + b"FOUND_ME"
pattern = b"FOUND_ME"

start = time.perf_counter()
indices = hex_search(data, pattern)
duration = (time.perf_counter() - start) * 1000

assert indices == [500000, 1000008], f"Incorrect results: {indices}"
print(f"Verification Successful: {len(indices)} matches found.")
"""
    
    if not orchestrator.get_skill("hex_search"):
        ExecutionLogger.log("REGISTRY", "Registering default 'hex_search' skill...")
        orchestrator.register_or_update_skill(
            "hex_search", 
            "Searches bytes for a pattern and returns all match starting indices.", 
            slow_search_code
        )

    if len(sys.argv) > 1 and sys.argv[1] == "--evolve":
        if not orchestrator.has_api_access():
            ExecutionLogger.log("ORCHESTRATOR", "Error: GEMINI_API_KEY env var is required.", "ERROR")
            sys.exit(1)
        orchestrator.run_evolution_step("hex_search", harness_code)
    else:
        ExecutionLogger.log("ORCHESTRATOR", "Registered Skills:")
        for name, desc, ver in orchestrator.get_all_skills():
            ExecutionLogger.log("ORCHESTRATOR", f"  - {name} (Version {ver}): {desc}")

# Enforce strict constant-time lookup for infrastructure security boundaries
EXCLUDED_SKILLS = frozenset({
    "main", "run_loop", "setUp", "tearDown", "test_self_patching",
    "check_status", "list_skills", "list_branches", "show_failures",
    "monitor", "compile_report", "safe_api_call", "send_message",
    "run_analytical_chat", "__init__", "mutate_math_in_code",
    "generate_math_mutations", "optimize_math_ast", "mutate_math_llm",
    "mutate_qubo_in_code", "generate_qubo_mutations", "optimize_qubo_ast",
    "mutate_qubo_llm"
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
    main()
