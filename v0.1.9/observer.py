import os
import sys
import sqlite3
import datetime
import json
from typing import Dict, Any, List
from orchestrator import Orchestrator, DB_PATH
from logger import ExecutionLogger

class EvolutionObserver:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.orchestrator = Orchestrator(db_path=db_path)

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def gather_telemetry_data(self) -> Dict[str, Any]:
        """Gathers comprehensive logs and database statistics on processes, mutations, and telemetry."""
        conn = self._get_conn()
        cursor = conn.cursor()
        data = {}

        try:
            # 1. Active Skills
            cursor.execute("SELECT skill_name, version, length(code) FROM active_skills")
            skills = cursor.fetchall()
            data["skills"] = [
                {"name": s[0], "version": s[1], "code_length": s[2]}
                for s in skills
            ]

            # 2. Mutation Branch Statistics
            cursor.execute("""
                SELECT status, COUNT(*), AVG(latency_ms), AVG(max_rss_kb) 
                FROM skill_branches 
                GROUP BY status
            """)
            branches = cursor.fetchall()
            data["mutation_summary"] = [
                {"status": b[0], "count": b[1], "avg_latency_ms": b[2] or 0.0, "avg_max_rss_kb": b[3] or 0.0}
                for b in branches
            ]

            # 3. Sandbox Reality Tests
            cursor.execute("SELECT status, COUNT(*) FROM reality_tests GROUP BY status")
            tests = cursor.fetchall()
            data["sandbox_tests"] = [{"status": t[0], "count": t[1]} for t in tests]

            # Fetch recent sandbox failure tracebacks to observe compilation issues
            cursor.execute("SELECT script_name, stderr, timestamp FROM reality_tests WHERE status = 'FAIL' ORDER BY id DESC LIMIT 5")
            failures = cursor.fetchall()
            data["recent_failures"] = [
                {"script": f[0], "stderr": f[1], "timestamp": f[2]}
                for f in failures
            ]

            # 4. API Request Telemetry
            cursor.execute("SELECT COUNT(*), SUM(tpm), AVG(latency_ms) FROM limit_telemetry")
            telemetry = cursor.fetchone()
            data["api_usage"] = {
                "total_calls": telemetry[0] if telemetry else 0,
                "total_tokens": telemetry[1] if telemetry and telemetry[1] is not None else 0,
                "avg_api_latency_ms": telemetry[2] if telemetry and telemetry[2] is not None else 0.0
            }

        except Exception as e:
            ExecutionLogger.log("OBSERVER", f"Failed to gather database statistics: {e}", "ERROR")
            data["error"] = str(e)
        finally:
            conn.close()

        return data

    def generate_report(self) -> str:
        """Constructs an observation report using Gemini based on gathered telemetry."""
        telemetry_data = self.gather_telemetry_data()

        # Build prompt for LLM report synthesis
        system_instruction = (
            "You are Project Hermit's Evolution Observer Agent.\n"
            "Your task is to analyze the gathered system execution metrics, sandbox runs, mutation histories, and API usage stats,\n"
            "and construct a highly detailed, professional markdown report analyzing the system's progress, failures, and recommendations."
        )

        prompt = f"""
        Analyze the following telemetry and mutation logs for Project Hermit:

        TELEMETRY METRICS:
        {json.dumps(telemetry_data, indent=2)}

        INSTRUCTIONS:
        1. Write a comprehensive report in GitHub-flavored markdown.
        2. Analyze the evolutionary behavior: which skills are optimized, the success vs. failure rates of proposed mutations, and common compiler/sandbox failures.
        3. Highlight the efficiency gains (latency and memory reductions) achieved by math and QUBO mutations.
        4. Recommend future optimization targets and rule enhancements based on the logs.
        5. Output ONLY the markdown report content.
        """

        res = self.orchestrator.call_gemini_api(prompt, system_instruction)
        if not res["success"]:
            err_msg = f"Failed to generate report via Gemini: {res['error']}"
            ExecutionLogger.log("OBSERVER", err_msg, "ERROR")
            return f"# Evolution Observation Report (API Failure)\n\nError: {res['error']}"

        report_content = res["text"].strip()
        
        # Save to file with timestamp in name
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"evolution_report_{timestamp}.md"
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)

        ExecutionLogger.log("OBSERVER", f"Observation report successfully written to: {filename}", "SUCCESS")
        return report_content

if __name__ == "__main__":
    observer = EvolutionObserver()
    print("Gathering telemetry and writing evolution report...")
    report = observer.generate_report()
    print("Report generated successfully.")
