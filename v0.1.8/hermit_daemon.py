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
        self.consecutive_attempts = {}
        self.thermal_history = []
        self.parallelism = 2
        self.start_time = time.time()
        self.start_time_sqlite = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')

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

    def mark_skill_explored(self, skill_name: str, reason: str):
        """Marks an untouched skill as explored/trivial/untestable so it is skipped by the first-pass scheduler."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT description FROM active_skills WHERE skill_name = ?", (skill_name,))
            row = cursor.fetchone()
            if row:
                desc = row[0]
                if "RESEARCH_STATUS" not in desc:
                    new_desc = f"{desc}\n\n=== RESEARCH_STATUS ===\nStatus: EXPLORED_TRIVIAL_OR_UNTESTABLE\nReason: {reason}\n"
                    cursor.execute("UPDATE active_skills SET description = ? WHERE skill_name = ?", (new_desc, skill_name))
                    conn.commit()
                    ExecutionLogger.log("DAEMON", f"Skill '{skill_name}' marked as: EXPLORED_TRIVIAL_OR_UNTESTABLE", "SUCCESS")
        except Exception as e:
            ExecutionLogger.log("DAEMON", f"Failed to mark skill explored: {e}", "ERROR")
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

    def get_thermal_state(self) -> float:
        import glob
        temps = []
        for zone in glob.glob('/sys/class/thermal/thermal_zone*/temp'):
            try:
                with open(zone, 'r') as f:
                    content = f.read().strip()
                    if content:
                        val = float(content) / 1000.0
                        if -50.0 <= val <= 150.0:
                            temps.append(val)
            except:
                pass
        return max(temps) if temps else 0.0

    def get_thermal_trend(self) -> float:
        """Calculates the temperature trend slope using simple linear regression or difference."""
        if len(self.thermal_history) < 2:
            return 0.0
        return (self.thermal_history[-1] - self.thermal_history[0]) / len(self.thermal_history)

    def adaptive_cooldown(self):
        """Predictively adjusts sleep cooldowns and sandbox parallelism based on temperature and trend slope."""
        import time
        temp = self.get_thermal_state()
        
        self.thermal_history.append(temp)
        if len(self.thermal_history) > 10:
            self.thermal_history.pop(0)
            
        slope = self.get_thermal_trend()
        
        # Determine cooldown sleep duration
        if temp > 70.0 or (temp > 60.0 and slope > 2.0):
            cooldown_time = 120.0
            self.broadcast_status("Throttled (Thermal Critical)")
        elif temp > 60.0 or slope > 1.0:
            cooldown_time = 60.0
            self.broadcast_status("Throttled (Thermal Warning)")
        elif temp > 55.0 or slope > 0.5:
            cooldown_time = 30.0
            self.broadcast_status("Throttled (Thermal Mild)")
        else:
            cooldown_time = 5.0 # normal cycle pause
            
        if cooldown_time > 5.0:
            ExecutionLogger.log("DAEMON", f"THERMAL_GUARD: CPU temp {temp:.1f}°C, trend slope {slope:.2f}°C/cycle. Sleeping for {cooldown_time}s...", "WARN")
            time.sleep(cooldown_time)
            
        # Sandbox parallelism setting (stored on daemon instance)
        if slope > 0.5:
            self.parallelism = 1
        else:
            self.parallelism = 2

    def calculate_latency_slope(self, merges: List[Tuple[float, float]]) -> float:
        if len(merges) < 2:
            return 0.0
        t0 = merges[0][0]
        xs = [(m[0] - t0) for m in merges]  # seconds
        ys = [m[1] for m in merges]
        y0 = ys[0] if ys[0] > 0 else 1.0
        ys_rel = [y / y0 for y in ys]
        
        n = len(xs)
        sum_x = sum(xs)
        sum_y = sum(ys_rel)
        sum_xx = sum(x*x for x in xs)
        sum_xy = sum(xs[i]*ys_rel[i] for i in range(n))
        
        denom = (n * sum_xx - sum_x * sum_x)
        if denom == 0:
            return ys_rel[-1] - ys_rel[0]
            
        slope_per_second = (n * sum_xy - sum_x * sum_y) / denom
        window_duration_seconds = 20 * 60
        return slope_per_second * window_duration_seconds

    def should_continue(self) -> bool:
        TOKEN_BUDGET = 5000000
        MAX_RUNTIME_SECONDS = 2 * 3600
        
        now = time.time()
        elapsed_seconds = now - self.start_time
        
        # 1. Hard bound: Max Runtime
        if elapsed_seconds > MAX_RUNTIME_SECONDS:
            ExecutionLogger.log("DAEMON", f"Runtime limit exceeded ({elapsed_seconds/3600:.2f} hours > {MAX_RUNTIME_SECONDS/3600:.2f} hours). Graceful shutdown.", "WARN")
            self.broadcast_status("Runtime limit reached")
            return False
            
        # 2. Hard bound: Token Budget
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(tpm) FROM limit_telemetry WHERE timestamp >= ? AND tpm IS NOT NULL", (self.start_time_sqlite,))
        row = cursor.fetchone()
        tokens_used = row[0] if (row and row[0] is not None) else 0
        if tokens_used > TOKEN_BUDGET:
            conn.close()
            ExecutionLogger.log("DAEMON", f"Token budget exceeded ({tokens_used} > {TOKEN_BUDGET}). Graceful shutdown.", "WARN")
            self.broadcast_status("Token budget exceeded")
            return False
            
        # 3. Global Convergence detection
        # Warmup period check: allow 20 minutes of execution before checking convergence
        IMPROVEMENT_WINDOW_MINUTES = 20
        if elapsed_seconds < IMPROVEMENT_WINDOW_MINUTES * 60:
            conn.close()
            return True
            
        # Get merges in the last 20 minutes
        cursor.execute("""
            SELECT strftime('%s', timestamp), latency_ms FROM skill_branches 
            WHERE status = 'merged' AND timestamp >= datetime('now', '-20 minutes')
            ORDER BY timestamp ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            ExecutionLogger.log("DAEMON", "No merges in the last 20 minutes. Global plateau detected. Initiating graceful shutdown.", "WARN")
            print("GLOBAL_PLATEAU_SHUTDOWN")
            self.broadcast_status("GLOBAL_PLATEAU_SHUTDOWN")
            return False
            
        merges = []
        for r_ts, r_lat in rows:
            try:
                merges.append((float(r_ts), float(r_lat)))
            except:
                pass
                
        if len(merges) >= 2:
            latency_trend = self.calculate_latency_slope(merges)
            MIN_IMPROVEMENT_THRESHOLD = 0.05  # 5% latency reduction
            if latency_trend > -MIN_IMPROVEMENT_THRESHOLD:
                ExecutionLogger.log("DAEMON", f"Global plateau detected (trend: {latency_trend*100:.2f}% improvement over 20 mins, threshold: {MIN_IMPROVEMENT_THRESHOLD*100:.2f}%). Initiating graceful shutdown.", "WARN")
                print("GLOBAL_PLATEAU_SHUTDOWN")
                self.broadcast_status("GLOBAL_PLATEAU_SHUTDOWN")
                return False
                
        return True

    def get_next_target(self) -> str:
        """Determines the next target skill using the v0.1.8 fairness scheduler.
        Phase 1: Every skill gets exactly one attempt before any gets two, sorted by optimization headroom.
        Phase 2: Bottleneck sort with fairness quota (cooldown on hot skills).
        """
        import random
        from orchestrator import DEFAULT_HARNESS
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Fetch all active skills
        cursor.execute("SELECT skill_name, description, code, baseline_latency, baseline_harness FROM active_skills")
        all_skills_data = cursor.fetchall()
        
        # Filter out excluded, complex, or failed skills
        viable_skills = []
        for name, desc, code, base_lat, base_harness in all_skills_data:
            if name in self.orchestrator.EXCLUDED_SKILLS:
                continue
            if self.consecutive_failures.get(name, 0) >= 3:
                continue
            if desc and "COMPLEX_NEEDS_FURTHER_RESEARCH" in desc:
                continue
            viable_skills.append({
                'name': name,
                'desc': desc,
                'code': code,
                'baseline_latency': base_lat,
                'baseline_harness': base_harness
            })
            
        if not viable_skills:
            conn.close()
            return None
            
        # 2. Compute merge count for each viable skill
        skills_with_merges = []
        untouched_skills = []
        
        for s in viable_skills:
            cursor.execute("SELECT COUNT(*) FROM skill_branches WHERE skill_name = ? AND status = 'merged'", (s['name'],))
            merge_count = cursor.fetchone()[0]
            s['merge_count'] = merge_count
            
            if merge_count == 0:
                untouched_skills.append(s)
            else:
                skills_with_merges.append(s)
                
        # Phase 1: Every skill gets exactly one attempt before any gets two
        if untouched_skills:
            # Gate: only attempt if skill has measurable work (latency > 1.0 or None) and has actual tests (assertions)
            viable_untouched = []
            for s in untouched_skills:
                # Count assertions in harness
                harness = s['baseline_harness'] or DEFAULT_HARNESS
                test_assertion_count = harness.count("assert")
                
                # We allow baseline_latency to be None (since it hasn't run yet)
                base_lat = s['baseline_latency']
                if (base_lat is None or base_lat > 1.0) and test_assertion_count > 0:
                    viable_untouched.append(s)
                else:
                    # Mark explored as insignificant or untestable
                    conn.close()
                    self.mark_skill_explored(s['name'], reason="insignificant_or_untestable")
                    conn = self._get_conn()
                    cursor = conn.cursor()
                    
            if viable_untouched:
                # Sort by optimization headroom: latency * code_complexity
                # If latency is None, assume a default of 10.0 ms for sorting headroom
                def get_headroom(s):
                    lat = s['baseline_latency'] if s['baseline_latency'] is not None else 10.0
                    comp = len(s['code']) if s['code'] else 1
                    return lat * comp
                
                viable_untouched.sort(key=get_headroom, reverse=True)
                chosen_skill = viable_untouched[0]['name']
                conn.close()
                ExecutionLogger.log("DAEMON", f"Selected target '{chosen_skill}' using strategy: Phase 1 (Untouched Headroom)", "INFO")
                # Increment consecutive attempts
                self.consecutive_attempts[chosen_skill] = self.consecutive_attempts.get(chosen_skill, 0) + 1
                return chosen_skill

        # Phase 2: Bottleneck sort with fairness quota
        # Retrieve current average latency from database
        active_skills_list = []
        for s in viable_skills:
            cursor.execute("""
                SELECT AVG(CAST(json_extract(metrics, '$.duration_ms') AS REAL)) 
                FROM reality_tests 
                WHERE script_name LIKE ? AND status = 'PASS'
            """, (f"%{s['name']}%",))
            row = cursor.fetchone()
            curr_lat = row[0] if (row and row[0] is not None) else (s['baseline_latency'] or 0.0)
            s['current_latency'] = curr_lat
            active_skills_list.append(s)
            
        conn.close()
        
        # Sort by current latency descending
        active_skills_list.sort(key=lambda x: x['current_latency'], reverse=True)
        
        # Prevent top skill from monopolizing
        MAX_CONSECUTIVE = 3
        chosen_skill = None
        for s in active_skills_list:
            name = s['name']
            attempts = self.consecutive_attempts.get(name, 0)
            if attempts < MAX_CONSECUTIVE:
                chosen_skill = name
                break
                
        if not chosen_skill and active_skills_list:
            # Force cooldown on all hot skills: clear/reset attempts and select a random fallback
            for s in active_skills_list:
                self.consecutive_attempts[s['name']] = 0
            chosen_skill = random.choice(active_skills_list)['name']
            ExecutionLogger.log("DAEMON", f"All hot skills throttled. Selected target '{chosen_skill}' using random fallback", "INFO")
        else:
            ExecutionLogger.log("DAEMON", f"Selected target '{chosen_skill}' using strategy: Phase 2 (Bottleneck Sort: {s['current_latency']:.2f}ms)", "INFO")
            
        if chosen_skill:
            # Reset consecutive attempts for other skills to keep it local to the active running target
            for name in list(self.consecutive_attempts.keys()):
                if name != chosen_skill:
                    self.consecutive_attempts[name] = 0
            self.consecutive_attempts[chosen_skill] = self.consecutive_attempts.get(chosen_skill, 0) + 1
            
        return chosen_skill

    def run_loop(self):
        ExecutionLogger.log("DAEMON", "Starting Project Hermit background daemon loop...", "SUCCESS")
        
        while self.should_continue():
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
                            clean_desc = desc
                            if "=== RESEARCH_STATUS ===" in desc:
                                clean_desc = desc.split("=== RESEARCH_STATUS ===")[0].strip()
                            if "=== HARNESS ===" in clean_desc:
                                parts = clean_desc.split("=== HARNESS ===")
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
                        # Correlate bottleneck latency to choose target using get_next_target
                        target = self.get_next_target()
                        if not target:
                            ExecutionLogger.log("DAEMON", "All bottleneck targets are cooling down or categorized as complex. Triggering independent research agent...", "INFO")
                            self.run_meta_research_on_complex_skills()
                            self.consecutive_failures.clear()
                            self.clear_complex_categorizations()
                            target = self.get_next_target()
 
                        if target:
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
                            ExecutionLogger.log("DAEMON", "No target selected. Standing by...")
                    else:
                        ExecutionLogger.log("DAEMON", "No active skills registered or discovered. Standing by...")
                
                # 4. Throttling / Limits Defense
                rpd, rpm, tpm = self.orchestrator.get_rolling_telemetry()
                
                # Ceiling guards: 12 RPM (safety buffer), 200k TPM
                if rpm >= 12 or tpm >= 200000:
                    sleep_time = 60.0
                    ExecutionLogger.log("DAEMON", f"Throttling triggered: {rpm} RPM, {tpm} TPM. Sleeping for {sleep_time}s to reset limit windows...", "WARN")
                    self.broadcast_status("Throttled (Limits Guard)")
                    time.sleep(sleep_time)
                    # Adaptive thermal-aware throttling
                    self.adaptive_cooldown()

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
