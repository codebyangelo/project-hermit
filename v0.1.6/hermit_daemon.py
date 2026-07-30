import os
import sys
import time
import sqlite3
import datetime
from typing import List, Tuple
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
        self.consecutive_failures = {}

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

    def get_bottleneck_skills(self) -> List[Tuple[str, float]]:
        """Queries the reality_tests database to identify the slowest skills based on average latency."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Select active skills and their latest pass latency
        cursor.execute("SELECT skill_name, description FROM active_skills")
        rows = cursor.fetchall()
        
        skills_with_latency = []
        for name, desc in rows:
            if name in self.orchestrator.EXCLUDED_SKILLS:
                continue
            if self.consecutive_failures.get(name, 0) >= 3:
                continue
            if desc and "COMPLEX_NEEDS_FURTHER_RESEARCH" in desc:
                continue
            # Fetch average latency of PASS tests for this skill
            cursor.execute("""
                SELECT AVG(CAST(json_extract(metrics, '$.duration_ms') AS REAL)) 
                FROM reality_tests 
                WHERE script_name LIKE ? AND status = 'PASS'
            """, (f"%{name}%",))
            row = cursor.fetchone()
            avg_latency = row[0] if (row and row[0] is not None) else 0.0
            skills_with_latency.append((name, avg_latency))
            
        conn.close()
        # Sort by average latency descending (slowest first)
        skills_with_latency.sort(key=lambda x: x[1], reverse=True)
        return skills_with_latency

    def mark_skill_complex_needs_research(self, skill_name: str, reasons: str):
        """Marks a skill in a dedicated metadata log/notes as requiring deeper research, cooling it down."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Check if description holds notes
            cursor.execute("SELECT description, code FROM active_skills WHERE skill_name = ?", (skill_name,))
            row = cursor.fetchone()
            if row:
                desc, code = row[0], row[1]
                if "RESEARCH_STATUS" not in desc:
                    new_desc = f"{desc}\n\n=== RESEARCH_STATUS ===\nStatus: COMPLEX_NEEDS_FURTHER_RESEARCH\nReasons:\n{reasons}\n"
                    cursor.execute("UPDATE active_skills SET description = ? WHERE skill_name = ?", (new_desc, skill_name))
                    conn.commit()
                    ExecutionLogger.log("DAEMON", f"Skill '{skill_name}' marked as: COMPLEX_NEEDS_FURTHER_RESEARCH", "SUCCESS")
        except Exception as e:
            ExecutionLogger.log("DAEMON", f"Failed to mark skill research status: {e}", "ERROR")
        finally:
            conn.close()

    def clear_complex_categorizations(self):
        """Removes the complex categorization notes from all active skills description fields."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT skill_name, description FROM active_skills")
            rows = cursor.fetchall()
            for name, desc in rows:
                if desc and "=== RESEARCH_STATUS ===" in desc:
                    # Strip the research status notes
                    clean_desc = desc.split("=== RESEARCH_STATUS ===")[0].strip()
                    cursor.execute("UPDATE active_skills SET description = ? WHERE skill_name = ?", (clean_desc, name))
            conn.commit()
            ExecutionLogger.log("DAEMON", "Cleared all COMPLEX_NEEDS_FURTHER_RESEARCH statuses.", "SUCCESS")
        except Exception as e:
            ExecutionLogger.log("DAEMON", f"Failed to clear complex categorizations: {e}", "ERROR")
        finally:
            conn.close()

    def run_meta_research_on_complex_skills(self):
        """Runs the independent researcher agent to analyze sandbox failures for all complex-marked skills."""
        ExecutionLogger.log("DAEMON", "Initiating independent research on all complex-status skills...", "INFO")
        self.broadcast_status("Researching complex failures")
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name, description, code FROM active_skills WHERE description LIKE '%COMPLEX_NEEDS_FURTHER_RESEARCH%'")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            ExecutionLogger.log("DAEMON", "No complex skills found to research.", "INFO")
            return
            
        from researcher import EvolutionResearcher
        researcher = EvolutionResearcher(db_path=self.db_path, orchestrator=self.orchestrator)
        
        for name, desc, code in rows:
            try:
                # Strip out research status tag/text to send the clean description to LLM
                clean_desc = desc
                if "=== RESEARCH_STATUS ===" in desc:
                    clean_desc = desc.split("=== RESEARCH_STATUS ===")[0].strip()
                
                ExecutionLogger.log("DAEMON", f"Researcher auditing failures for complex skill: '{name}'", "INFO")
                researcher.research_failures(name, code, clean_desc)
            except Exception as e:
                ExecutionLogger.log("DAEMON", f"Research failed for skill '{name}': {e}", "ERROR")

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
                    if not harness:
                        skill_info = self.orchestrator.get_skill(target_skill)
                        if skill_info:
                            desc = skill_info[0]
                            if "=== HARNESS ===" in desc:
                                parts = desc.split("=== HARNESS ===")
                                harness = parts[1].strip()
                    harness = harness if harness else DEFAULT_HARNESS
                    
                    ExecutionLogger.log("DAEMON", f"Received user intervention task: {prompt}")
                    self.broadcast_status(f"Processing Task: {prompt}")
                    self.update_intervention(task_id, "processing")
                    
                    if target_skill == "discover" or "discover" in prompt.lower():
                        ExecutionLogger.log("DAEMON", "Processing user discovery command...")
                        self.broadcast_status("Running user-requested skill discovery")
                        success, skill_name = self.orchestrator.discover_and_register_new_skill()
                        msg = f"Discovered and registered skill: {skill_name}" if success else f"Discovery failed: {skill_name}"
                    else:
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
                        # Correlate bottleneck latency to choose target
                        bottlenecks = self.get_bottleneck_skills()
                        if not bottlenecks:
                            ExecutionLogger.log("DAEMON", "All bottleneck targets are cooling down or categorized as complex. Triggering independent research agent...", "INFO")
                            self.run_meta_research_on_complex_skills()
                            self.consecutive_failures.clear()
                            self.clear_complex_categorizations()
                            bottlenecks = self.get_bottleneck_skills()

                        # Prioritize skills with 0.0 latency (unbenchmarked) first, then slowest first.
                        # Sort key: (is_unbenchmarked, latency_value)
                        bottlenecks.sort(key=lambda x: (x[1] == 0.0, x[1]), reverse=True)
                        target = bottlenecks[0][0]
                        
                        # Extract harness from the skill's description
                        skill_info = self.orchestrator.get_skill(target)
                        harness = DEFAULT_HARNESS
                        if skill_info:
                            desc = skill_info[0]
                            # Clean any research status tags from desc first to isolate the harness
                            clean_desc = desc
                            if "=== RESEARCH_STATUS ===" in desc:
                                clean_desc = desc.split("=== RESEARCH_STATUS ===")[0].strip()
                            if "=== HARNESS ===" in clean_desc:
                                parts = clean_desc.split("=== HARNESS ===")
                                harness = parts[1].strip()
                                
                        # Setup dynamic pivot instructions on subsequent failed attempts
                        failures_so_far = self.consecutive_failures.get(target, 0)
                        pivot_instruction = None
                        if failures_so_far == 1:
                            pivot_instruction = "Pivot: Focus on strict type-safety, import required modules (e.g. typing, re), and avoid NameErrors."
                            ExecutionLogger.log("DAEMON", f"Target '{target}' failed once. Retrying with pivot: {pivot_instruction}", "INFO")
                        elif failures_so_far == 2:
                            pivot_instruction = "Pivot: Focus on algebraic simplification, avoid complex regex pattern rewrites, and ensure backward compatibility."
                            ExecutionLogger.log("DAEMON", f"Target '{target}' failed twice. Retrying with pivot: {pivot_instruction}", "INFO")

                        self.broadcast_status(f"Optimizing skill: {target}")
                        success, msg = self.orchestrator.run_evolution_step(target, harness, user_instruction=pivot_instruction)
                        
                        if success:
                            self.consecutive_failures[target] = 0
                        else:
                            self.consecutive_failures[target] = self.consecutive_failures.get(target, 0) + 1
                            if self.consecutive_failures[target] >= 3:
                                # Categorize as "complex needs further research"
                                reasons = f"Failed 3 consecutive optimization attempts. Last run details: {msg}"
                                self.mark_skill_complex_needs_research(target, reasons)
                                self.consecutive_failures[target] = 0 # reset count since it is now categorized

                        # If optimization fails/plateaus (success = False), try to discover a new skill from codebase
                        if not success:
                            ExecutionLogger.log("DAEMON", f"Optimization for target '{target}' plateaued. Scanning codebase to discover other bottlenecks...", "INFO")
                            self.broadcast_status("Plateaued; Scanning for new bottlenecks")
                            self.orchestrator.discover_and_register_new_skill()
                        
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
