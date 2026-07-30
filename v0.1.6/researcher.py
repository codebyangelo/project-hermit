import sqlite3
import datetime
import traceback
from typing import Optional, Dict, Any
from logger import ExecutionLogger

class EvolutionResearcher:
    def __init__(self, db_path: str, orchestrator=None):
        self.db_path = db_path
        self.orchestrator = orchestrator

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def get_recent_failures(self, skill_name: str, limit: int = 3):
        """Fetches the latest failed executions for this skill from reality_tests."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT script_name, script_content, stderr, stdout, timestamp
            FROM reality_tests
            WHERE (script_name LIKE ? OR script_content LIKE ?) AND status = 'FAIL'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f"%{skill_name}%", f"%def {skill_name}%", limit))
        rows = cursor.fetchall()
        conn.close()
        
        failures = []
        for r in rows:
            failures.append({
                "script_name": r[0],
                "script_content": r[1],
                "stderr": r[2],
                "stdout": r[3],
                "timestamp": r[4]
            })
        return failures

    def research_failures(self, skill_name: str, current_code: str, skill_desc: str) -> Optional[str]:
        """Analyzes recent sandbox tracebacks and uses LLM to generate research notes/strategy."""
        failures = self.get_recent_failures(skill_name)
        if not failures:
            ExecutionLogger.log("RESEARCHER", f"No historical failures found for '{skill_name}' to research.", "INFO")
            return None

        # Build research prompt detailing the failure logs
        failures_str = ""
        for idx, f in enumerate(failures):
            failures_str += f"--- FAILURE ATTEMPT {idx + 1} ---\n"
            failures_str += f"Script Name: {f['script_name']}\n"
            failures_str += f"Crash Traceback (stderr):\n{f['stderr']}\n"
            if f['stdout']:
                failures_str += f"Output (stdout):\n{f['stdout']}\n"
            failures_str += "\n"

        system_instruction = (
            "You are a Principal Software Architect and Research Agent.\n"
            "Your job is to analyze failed self-evolution attempts for a Python utility, diagnose root causes, "
            "and write a concrete research strategy note to guide future optimization attempts.\n"
            "Identify standard library constraints (e.g. memoryview, structure unpacking, bitwise shifts), "
            "missing imports, and edge conditions (empty lists/bytes, zero bounds, null patterns).\n"
            "Provide clear code snippets, algorithmic outlines, or documentation hints. Do not write the full code, "
            "but give exact strategy guidelines."
        )

        prompt = f"""
        Analyze the recurring failures for the skill '{skill_name}'.
        
        SKILL DESCRIPTION:
        {skill_desc}

        CURRENT BASELINE CODE:
        ```python
        {current_code}
        ```

        SANDBOX FAILURE LOGS:
        {failures_str}

        Please construct a RESEARCH STRATEGY NOTE with:
        1. DIAGNOSIS: Root cause of the compilation or logic crash (e.g., specific missing attributes or type errors).
        2. ALGORITHMIC STRATEGY: Recommended standard library modules, functions, or patterns to resolve this issue correctly.
        3. BOUNDARY CASE DIRECTIVES: Directives for handling empty patterns, null bytes, zero bounds, and negative parameters.
        4. DESIGN PATTERNS TO AVOID: Specific code structures that failed previously and must not be repeated.
        """

        if not self.orchestrator:
            from orchestrator import Orchestrator
            self.orchestrator = Orchestrator(db_path=self.db_path)

        ExecutionLogger.log("RESEARCHER", f"Querying LLM Research Agent for '{skill_name}'...", "INFO")
        res = self.orchestrator.call_gemini_api(prompt, system_instruction)
        
        if res["success"]:
            notes = res["text"]
            self.store_research_note(skill_name, notes)
            ExecutionLogger.log("RESEARCHER", f"Research notes generated and saved for '{skill_name}'.", "SUCCESS")
            return notes
        else:
            ExecutionLogger.log("RESEARCHER", f"Failed to generate research notes for '{skill_name}': {res['error']}", "ERROR")
            return None

    def store_research_note(self, skill_name: str, notes: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO skill_research_notes (skill_name, notes, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (skill_name, notes))
        conn.commit()
        conn.close()

    def get_research_note(self, skill_name: str) -> Optional[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT notes FROM skill_research_notes WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
