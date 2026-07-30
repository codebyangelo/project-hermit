import os
import sys
import time
import sqlite3
import datetime
from orchestrator import Orchestrator, DB_PATH
from logger import ExecutionLogger

DEFAULT_HARNESS = """
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

class HermitDaemon:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.orchestrator = Orchestrator(db_path=db_path)

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def broadcast_status(self, status: str):
        """Updates the daemon_status table with the current state."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO daemon_status (id, status, last_updated)
            VALUES (1, ?, CURRENT_TIMESTAMP)
        """, (status,))
        conn.commit()
        conn.close()

    def get_pending_intervention(self):
        """Fetches the oldest pending user task."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, prompt, target_skill, verification_harness 
            FROM user_interventions 
            WHERE status = 'pending' 
            ORDER BY id ASC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return row

    def update_intervention(self, task_id: int, status: str, result: str = None):
        """Updates the status and results of a user task."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_interventions 
            SET status = ?, result = ?
            WHERE id = ?
        """, (status, result, task_id))
        conn.commit()
        conn.close()

    def check_and_apply_context_decay(self, skill_name: str):
        """Checks if a skill has failed > 3 times, summarizes failures, and purges logs."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Count failures in reality_tests
        cursor.execute("""
            SELECT COUNT(*) FROM reality_tests 
            WHERE script_name LIKE ? AND status = 'FAIL'
        """, (f"%{skill_name}%",))
        fail_count = cursor.fetchone()[0]
        
        if fail_count > 3:
            ExecutionLogger.log("DAEMON", f"Skill '{skill_name}' has {fail_count} failures. Initiating context decay...", "WARN")
            self.broadcast_status(f"Decaying context for {skill_name}")
            
            # Fetch last 3 failure logs (stderrs)
            cursor.execute("""
                SELECT stderr FROM reality_tests 
                WHERE script_name LIKE ? AND status = 'FAIL'
                ORDER BY id DESC LIMIT 3
            """, (f"%{skill_name}%",))
            failures = [r[0] for r in cursor.fetchall() if r[0]]
            
            summary = "Multiple script execution failures detected."
            if failures and self.orchestrator.has_api_access():
                prompt = (
                    f"Summarize the following compilation or execution errors for the skill '{skill_name}' in 2 sentences. "
                    "Focus only on the syntax/logic reasons for the crash.\n\n" + "\n---\n".join(failures)
                )
                res = self.orchestrator.call_gemini_api(prompt, "You are a debugging helper.")
                if res["success"]:
                    summary = res["text"].strip()

            # Append summary to description and purge raw tests
            cursor.execute("""
                UPDATE active_skills 
                SET description = description || '\n[Context Decay Summary]: ' || ?
                WHERE skill_name = ?
            """, (summary, skill_name))
            
            cursor.execute("""
                DELETE FROM reality_tests 
                WHERE script_name LIKE ?
            """, (f"%{skill_name}%",))
            
            ExecutionLogger.log("DAEMON", f"Context decay complete. Skill description updated, reality tests purged.", "SUCCESS")
        
        conn.commit()
        conn.close()

    def run_loop(self):
        ExecutionLogger.log("DAEMON", "Starting Project Hermit background daemon loop...", "SUCCESS")
        
        while True:
            try:
                # 1. Broadcaster
                self.broadcast_status("Idle")
                
                # 2. Check Interventions
                task = self.get_pending_intervention()
                
                if task:
                    task_id, prompt, target_skill, harness = task
                    target_skill = target_skill if target_skill else "hex_search"
                    harness = harness if harness else DEFAULT_HARNESS
                    
                    ExecutionLogger.log("DAEMON", f"Received user intervention task: {prompt}")
                    self.broadcast_status(f"Processing Task: {prompt}")
                    self.update_intervention(task_id, "processing")
                    
                    # Run evolutionary step with user constraint
                    success, msg = self.orchestrator.run_evolution_step(
                        target_skill, 
                        harness, 
                        user_instruction=prompt
                    )
                    
                    status_verdict = "completed" if success else "failed"
                    self.update_intervention(task_id, status_verdict, result=msg)
                    ExecutionLogger.log("DAEMON", f"Intervention completed. Result: {msg}", "SUCCESS" if success else "WARN")
                    
                else:
                    # 3. Autonomous Execution
                    self.broadcast_status("Selecting target skill for autonomous optimization")
                    skills = self.orchestrator.get_all_skills()
                    
                    if not skills:
                        self.broadcast_status("No skills exist. Running autonomous skill discovery...")
                        success, discovered_skill = self.orchestrator.discover_and_register_new_skill()
                        if success:
                            skills = self.orchestrator.get_all_skills()
                        else:
                            ExecutionLogger.log("DAEMON", "Autonomous skill discovery failed.", "WARN")
                    
                    if skills:
                        target = skills[0][0]
                        
                        # Extract harness from the skill's description
                        skill_info = self.orchestrator.get_skill(target)
                        harness = DEFAULT_HARNESS
                        if skill_info:
                            desc = skill_info[0]
                            if "=== HARNESS ===" in desc:
                                parts = desc.split("=== HARNESS ===")
                                harness = parts[1].strip()
                                
                        self.broadcast_status(f"Optimizing skill: {target}")
                        self.orchestrator.run_evolution_step(target, harness)
                        
                        # Check context decay conditions
                        self.check_and_apply_context_decay(target)
                    else:
                        ExecutionLogger.log("DAEMON", "No active skills registered or discovered. Standing by...")
                
                # 4. Throttling / Limits Defense
                rpd, rpm, tpm = self.orchestrator.get_rolling_telemetry()
                
                # Ceiling guards: 15 RPM, 250k TPM
                if rpm >= 12 or tpm >= 200000:
                    sleep_time = 60.0
                    ExecutionLogger.log("DAEMON", f"Throttling triggered: {rpm} RPM, {tpm} TPM. Sleeping for {sleep_time}s to reset limit windows...", "WARN")
                    self.broadcast_status("Throttled (Limits Guard)")
                else:
                    sleep_time = 5.0  # Default heartbeat sleep
                    self.broadcast_status("Idle (Heartbeat Sleep)")
                    
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                ExecutionLogger.log("DAEMON", "Daemon terminated by user.", "SUCCESS")
                self.broadcast_status("Stopped")
                break
            except Exception as e:
                ExecutionLogger.log("DAEMON", f"Unexpected loop exception: {e}", "ERROR")
                self.broadcast_status("Error: Loop crashed")
                time.sleep(10.0)

if __name__ == "__main__":
    daemon = HermitDaemon()
    daemon.run_loop()
