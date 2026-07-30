import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error
import datetime
from typing import Dict, Any, List, Optional, Tuple

from sandbox import run_in_sandbox, SandboxResult
from logger import ExecutionLogger

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")

class Orchestrator:
    """
    Project Hermit Orchestrator.
    Controls the Gemini API interface, monitors rate/token limits, manages database state,
    and runs the evolutionary mutation loop inside the sandbox.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        # Respect GEMINI_MODEL env var or default to gemini-2.5-flash
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    def has_api_access(self) -> bool:
        return len(self.api_key.strip()) > 0

    def get_rolling_telemetry(self) -> Tuple[int, int, int]:
        """
        Calculates actual rolling telemetry from the database:
        - Requests in the last 24 hours (RPD)
        - Requests in the last 60 seconds (RPM)
        - Sum of tokens used in the last 60 seconds (TPM)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # RPD: Count requests in the last 24 hours
        cursor.execute("""
            SELECT COUNT(*) FROM limit_telemetry 
            WHERE timestamp >= datetime('now', '-1 day')
        """)
        rpd = cursor.fetchone()[0]

        # RPM: Count requests in the last 60 seconds
        cursor.execute("""
            SELECT COUNT(*) FROM limit_telemetry 
            WHERE timestamp >= datetime('now', '-1 minute')
        """)
        rpm = cursor.fetchone()[0]

        # TPM: Sum of tokens (prompt + completion stored in tpm) in the last 60 seconds
        cursor.execute("""
            SELECT SUM(tpm) FROM limit_telemetry 
            WHERE timestamp >= datetime('now', '-1 minute') AND tpm IS NOT NULL
        """)
        tpm_sum = cursor.fetchone()[0]
        tpm = tpm_sum if tpm_sum is not None else 0

        conn.close()
        return rpd, rpm, tpm

    def log_api_call(self, rpd: int, rpm: int, tpm_used: int, error_code: Optional[str], latency_ms: int, notes: str):
        """Logs the API call metrics to the limit_telemetry table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO limit_telemetry (rpd, rpm, tpm, error_code, latency_ms, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (rpd, rpm, tpm_used, error_code, latency_ms, notes))
        conn.commit()
        conn.close()

    def call_gemini_api(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """
        Makes a direct, zero-dependency POST request to the Gemini generateContent API.
        Tracks rate limit telemetry and updates the database.
        """
        if not self.has_api_access():
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        rpd_before, rpm_before, tpm_before = self.get_rolling_telemetry()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )

        start_time = time.perf_counter()
        error_code = None
        tpm_used = 0
        response_text = ""
        notes = f"Model: {self.model}"

        try:
            with urllib.request.urlopen(req) as response:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                res_body = json.loads(response.read().decode("utf-8"))
                
                # Parse generation result text
                candidates = res_body.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        response_text = parts[0].get("text", "")
                
                # Parse token usage metadata
                usage = res_body.get("usageMetadata", {})
                tpm_used = usage.get("totalTokenCount", 0)
                prompt_tokens = usage.get('promptTokenCount', 0)
                candidates_tokens = usage.get('candidatesTokenCount', 0)
                ExecutionLogger.add_tokens(prompt_tokens, candidates_tokens)
                notes += f" | Prompt Tokens: {prompt_tokens}, Candidates: {candidates_tokens}"
                
                self.log_api_call(rpd_before + 1, rpm_before + 1, tpm_used, None, latency_ms, notes)
                ExecutionLogger.log("LLM_CLIENT", f"Gemini API call successful: {prompt_tokens} prompt tokens, {candidates_tokens} completion tokens. Latency: {latency_ms}ms")
                
                return {
                    "success": True,
                    "text": response_text,
                    "tokens": tpm_used,
                    "latency_ms": latency_ms
                }

        except urllib.error.HTTPError as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error_code = f"HTTP {e.code}"
            err_msg = e.read().decode("utf-8") if e.fp else e.reason
            self.log_api_call(rpd_before + 1, rpm_before + 1, 0, error_code, latency_ms, f"HTTP Error: {err_msg}")
            ExecutionLogger.log("LLM_CLIENT", f"Gemini API call failed: {error_code} - {err_msg}", "ERROR")
            return {
                "success": False,
                "text": "",
                "tokens": 0,
                "latency_ms": latency_ms,
                "error": f"{error_code}: {err_msg}"
            }
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error_code = "Exception"
            self.log_api_call(rpd_before + 1, rpm_before + 1, 0, error_code, latency_ms, f"Exception: {str(e)}")
            ExecutionLogger.log("LLM_CLIENT", f"Gemini API call exception: {str(e)}", "ERROR")
            return {
                "success": False,
                "text": "",
                "tokens": 0,
                "latency_ms": latency_ms,
                "error": str(e)
            }

    def register_or_update_skill(self, skill_name: str, description: str, code: str) -> bool:
        """Saves or updates a skill in the active_skills registry table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if the skill already exists to increment the version
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
            cursor.execute("""
                INSERT INTO active_skills (skill_name, description, code, version)
                VALUES (?, ?, ?, 1)
            """, (skill_name, description, code))
            action = "registered"
            
        conn.commit()
        conn.close()
        ExecutionLogger.log("REGISTRY", f"Skill '{skill_name}' successfully {action} (Version {version if row else 1}).", "SUCCESS")
        return True

    def get_skill(self, skill_name: str) -> Optional[Tuple[str, str, int]]:
        """Retrieves a skill from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT description, code, version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_all_skills(self) -> List[Tuple[str, str, int]]:
        """Retrieves all registered skills from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name, description, version FROM active_skills")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def run_evolution_step(self, skill_name: str, verification_harness: str):
        """
        Executes a single evolution mutation step:
        1. Retrieves the baseline skill implementation and active state.
        2. Prompts Gemini to generate an optimized version.
        3. Executes the mutation in the sandbox against the verification_harness.
        4. Compares performance metrics (latency and memory).
        5. Registers the mutation if it passes and is more efficient.
        """
        skill_info = self.get_skill(skill_name)
        if not skill_info:
            ExecutionLogger.log("ORCHESTRATOR", f"Skill '{skill_name}' is not registered.", "ERROR")
            return

        desc, base_code, version = skill_info
        ExecutionLogger.log("ORCHESTRATOR", f"Starting Evolution Cycle for Skill: {skill_name} (Current Version: {version})")

        # Run current baseline inside the sandbox first to get baseline performance metrics
        baseline_run_script = f"{base_code}\n\n{verification_harness}"
        ExecutionLogger.log("ORCHESTRATOR", "Running baseline implementation in sandbox...")
        baseline_result = run_in_sandbox(baseline_run_script, "baseline_verify.py")
        baseline_result.log_to_db(self.db_path)

        if baseline_result.exit_code != 0:
            ExecutionLogger.log("ORCHESTRATOR", "Baseline implementation failed verification tests!", "ERROR")
            ExecutionLogger.log("ORCHESTRATOR", f"Stderr:\n{baseline_result.stderr}", "ERROR")
            return

        ExecutionLogger.log("ORCHESTRATOR", f"Baseline performance: Duration = {baseline_result.duration_ms:.2f} ms, Max RSS = {baseline_result.max_rss_kb} KB", "SUCCESS")

        if not self.has_api_access():
            ExecutionLogger.log("ORCHESTRATOR", "No GEMINI_API_KEY detected. Skipping evolutionary query.", "WARN")
            return

        # Prepare evolutionary prompt
        system_instruction = (
            "You are Project Hermit's Evolutionary Synthesizer.\n"
            "Your task is to optimize Python code mutations for maximum speed, minimal token usage, and minimal memory overhead.\n"
            "You must return your output ONLY as a valid JSON object matching the requested schema. No prose, no markdown formatting."
        )

        prompt = f"""
        Optimize the following Python skill implementation named '{skill_name}'.
        
        DESCRIPTION:
        {desc}

        BASELINE CODE:
        ```python
        {base_code}
        ```

        VERIFICATION HARNESS RUN AGAINST IT:
        ```python
        {verification_harness}
        ```

        BASELINE METRICS ACHIEVED:
        - Execution Time: {baseline_result.duration_ms:.2f} ms
        - Memory Usage: {baseline_result.max_rss_kb} KB

        INSTRUCTIONS:
        1. Modify/optimize the skill code to reduce execution latency and RAM footprint.
        2. Maintain functional compliance. The mutated code must compile, execute, and pass all checks in the VERIFICATION HARNESS.
        3. Do NOT import third-party packages. Only use the Python standard library.
        4. Return your response as a valid JSON object matching this schema:
        {{
            "thought": "Explain your optimization rationale and changes.",
            "optimized_code": "The complete optimized Python code block containing the function definition."
        }}
        """

        ExecutionLogger.log("ORCHESTRATOR", "Querying Gemini API for optimized mutation...")
        res = self.call_gemini_api(prompt, system_instruction)
        if not res["success"]:
            ExecutionLogger.log("ORCHESTRATOR", f"API Error: {res['error']}", "ERROR")
            return

        try:
            clean_text = res["text"].strip()
            # Handle standard API markdown formatting if present
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            mutation_json = json.loads(clean_text)
            optimized_code = mutation_json["optimized_code"]
            rationale = mutation_json["thought"]
            ExecutionLogger.log("ORCHESTRATOR", f"Gemini Optimization Rationale: {rationale}")
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to parse mutation JSON response: {e}", "ERROR")
            ExecutionLogger.log("ORCHESTRATOR", f"Raw Response: {res['text']}", "ERROR")
            return

        # Build execution script with optimized code
        mutation_run_script = f"{optimized_code}\n\n{verification_harness}"
        ExecutionLogger.log("ORCHESTRATOR", "Testing mutation in sandbox...")
        mutation_result = run_in_sandbox(mutation_run_script, "mutation_verify.py")
        mutation_result.log_to_db(self.db_path)

        if mutation_result.exit_code != 0:
            ExecutionLogger.log("ORCHESTRATOR", "Mutation failed verification tests!", "ERROR")
            ExecutionLogger.log("ORCHESTRATOR", f"Stderr:\n{mutation_result.stderr}", "ERROR")
            return

        ExecutionLogger.log("ORCHESTRATOR", f"Mutation performance: Duration = {mutation_result.duration_ms:.2f} ms, Max RSS = {mutation_result.max_rss_kb} KB", "SUCCESS")

        # Decision Matrix: Integrate if it passes and runs faster or consumes less RAM
        if mutation_result.duration_ms < baseline_result.duration_ms:
            time_saved = baseline_result.duration_ms - mutation_result.duration_ms
            ExecutionLogger.log("ORCHESTRATOR", f"INTEGRATION SUCCESS: Mutation is faster by {time_saved:.2f} ms!", "SUCCESS")
            self.register_or_update_skill(skill_name, desc, optimized_code)
        elif mutation_result.max_rss_kb < baseline_result.max_rss_kb and mutation_result.duration_ms <= baseline_result.duration_ms * 1.05:
            ram_saved = baseline_result.max_rss_kb - mutation_result.max_rss_kb
            ExecutionLogger.log("ORCHESTRATOR", f"INTEGRATION SUCCESS: Mutation saved {ram_saved} KB of RAM!", "SUCCESS")
            self.register_or_update_skill(skill_name, desc, optimized_code)
        else:
            ExecutionLogger.log("ORCHESTRATOR", "INTEGRATION REJECTED: Mutation did not beat baseline metrics.", "WARN")


def main():
    ExecutionLogger.log("ORCHESTRATOR", "[ PROJECT HERMIT - Orchestrator Baseline ]", "SUCCESS")
    orchestrator = Orchestrator()

    # Register a default slow search skill if none exists
    slow_search_code = """
def hex_search(data_bytes: bytes, pattern: bytes) -> list:
    # A simple, inefficient O(N*M) naive search
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
# Verification testing harness
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

    # Simple CLI menu
    if len(sys.argv) > 1 and sys.argv[1] == "--evolve":
        if not orchestrator.has_api_access():
            ExecutionLogger.log("ORCHESTRATOR", "Error: GEMINI_API_KEY environment variable is required to run evolution.", "ERROR")
            sys.exit(1)
        orchestrator.run_evolution_step("hex_search", harness_code)
    else:
        ExecutionLogger.log("ORCHESTRATOR", "Registered Skills:")
        for name, desc, ver in orchestrator.get_all_skills():
            ExecutionLogger.log("ORCHESTRATOR", f"  - {name} (Version {ver}): {desc}")
        ExecutionLogger.log("ORCHESTRATOR", "To run the evolution cycle, set the GEMINI_API_KEY env var and run:")
        ExecutionLogger.log("ORCHESTRATOR", "  python3 orchestrator.py --evolve")

if __name__ == "__main__":
    main()
