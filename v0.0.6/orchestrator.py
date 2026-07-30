import os
import sys
import json
import time
import sqlite3
import datetime
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from sandbox import run_in_sandbox, SandboxResult
from logger import ExecutionLogger

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")

class Orchestrator:
    """
    Project Hermit Orchestrator v0.0.3.
    Uses Google GenAI SDK's Interactions API to manage multi-agent evolutionary mutations.
    Integrates an Adversarial QA Agent and Genetic Branching (multi-candidate variants).
    """
    # Class-level variable to enforce strict pacing between any API calls across instances
    LAST_CALL_TIME = 0.0

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        # Default model to gemini-3.1-flash-lite
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

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
        """
        if not self.has_api_access():
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        # Enforce strict 5.0 second pacing guard
        current_time = time.time()
        time_since_last = current_time - Orchestrator.LAST_CALL_TIME
        if time_since_last < 5.0:
            sleep_needed = 5.0 - time_since_last
            ExecutionLogger.log("LLM_CLIENT", f"Rate limit defense: Pacing API call. Sleeping for {sleep_needed:.2f}s...")
            time.sleep(sleep_needed)

        rpd_before, rpm_before, tpm_before = self.get_rolling_telemetry()
        start_time = time.perf_counter()
        
        try:
            # Initialize the official SDK client
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
            ExecutionLogger.log("LLM_CLIENT", f"Interactions API call exception: {str(e)}", "ERROR")
            return {
                "success": False,
                "text": "",
                "tokens": 0,
                "latency_ms": latency_ms,
                "error": str(e)
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

    def get_skill(self, skill_name: str) -> Optional[Tuple[str, str, int]]:
        """Retrieves a skill from the database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT description, code, version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_all_skills(self) -> List[Tuple[str, str, int]]:
        """Retrieves all registered skills from the database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name, description, version FROM active_skills")
        rows = cursor.fetchall()
        conn.close()
        return rows

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
            return False, err

        baseline_complexity = len(base_code)
        ExecutionLogger.log("ORCHESTRATOR", f"Baseline performance: Latency = {baseline_result.duration_ms:.2f} ms | RAM = {baseline_result.max_rss_kb} KB | Complexity = {baseline_complexity} chars", "SUCCESS")

        if not self.has_api_access():
            err = "No GEMINI_API_KEY detected. Aborting evolution."
            ExecutionLogger.log("ORCHESTRATOR", err, "WARN")
            return False, err

        # 2. Query QA Agent to generate adversarial assertions and verify them against baseline
        try:
            max_retries = 3
            verified_test_code = None
            for attempt in range(1, max_retries + 1):
                adversarial_test_code = self.generate_adversarial_tests(skill_name, desc, base_code)
                
                # Verify that the baseline code passes the generated adversarial checks
                validation_script = f"{base_code}\n\n{adversarial_test_code}"
                validation_result = run_in_sandbox(validation_script, "baseline_self_verify.py")
                
                if validation_result.exit_code == 0:
                    ExecutionLogger.log("QA_AGENT", f"Adversarial QA checks successfully verified against baseline on attempt {attempt}.", "SUCCESS")
                    verified_test_code = adversarial_test_code
                    break
                else:
                    ExecutionLogger.log("QA_AGENT", f"Discarded hallucinated QA test on attempt {attempt}: Failed baseline validation. Stderr: {validation_result.stderr}", "WARN")
            
            if verified_test_code is None:
                err = "Adversarial QA generation failed: QA Agent repeatedly generated hallucinated assertions that the baseline itself fails."
                ExecutionLogger.log("QA_AGENT", err, "ERROR")
                return False, err
                
            # Save it to history database to prevent future regressions!
            self.save_adversarial_test(skill_name, verified_test_code)
        except Exception as e:
            err = f"Adversarial QA generation failed: {e}"
            ExecutionLogger.log("QA_AGENT", err, "ERROR")
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
        except Exception as e:
            err = f"Failed to parse variants JSON: {e}"
            ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
            return False, err

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

            # Run in sandbox
            result = run_in_sandbox(full_test_script, f"{branch_name}_verify.py")
            result.log_to_db(self.db_path)
            
            complexity = len(code)
            
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

        # 5. Select the best branch and merge
        if not valid_candidates:
            msg = "INTEGRATION REJECTED: No variants passed all adversarial tests and optimized metrics."
            ExecutionLogger.log("ORCHESTRATOR", msg, "WARN")
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
        
        msg = f"INTEGRATION SUCCESS: Merged branch '{best['branch_name']}' (Latency: {best['latency']:.2f}ms, RAM: {best['rss']}KB, Score: {best['score']:.2f})"
        ExecutionLogger.log("ORCHESTRATOR", msg, "SUCCESS")
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

if __name__ == "__main__":
    main()
