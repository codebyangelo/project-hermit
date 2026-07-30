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

def write_thought_ledger(phase: str, component: str, details: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
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
        "select_api_key",
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

    IMMUTABLE_FUNCTIONS = frozenset({
        "is_significant_improvement",  # The gatekeeper
        "calculate_latency_slope",     # The metric calculator
        "get_next_target",             # The scheduler
        "sandbox_run",                 # The verifier
        "detect_oscillation",          # The stability guard
        "discover_and_register_new_skill",
        "register_or_update_skill",
        "patch_source_file_with_skill"
    })

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.api_keys = []
        
        # 1. Load keys from api_keys.txt in the current directory if it exists
        keys_file = "api_keys.txt"
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r") as f:
                    for line in f:
                        key = line.strip()
                        if key and not key.startswith("#"):
                            self.api_keys.append(key)
            except Exception as e:
                ExecutionLogger.log("LLM_CLIENT", f"Error reading keys file {keys_file}: {e}", "WARN")
                
        # 2. Fallback to environment variable
        if not self.api_keys:
            env_key = os.environ.get("GEMINI_API_KEY", "")
            if env_key:
                self.api_keys.append(env_key)
                
        self.active_key_index = 0
        self.model = "gemini-3.1-flash-lite"

        # Initialize key pool statistics
        now_time = time.time()
        self.key_stats = {
            k: {
                'rpm_minute': [],  # list of timestamps
                'tpm_minute': 0,
                'daily_tpm': 0,
                'last_reset': now_time,
                'last_tpm_reset': now_time,
                'total_calls': 0
            }
            for k in self.api_keys
        }

        # Verify database integrity and load backup if corrupted
        self._last_backup_time = now_time
        self.verify_database()
        
        # Backup the database on startup as baseline
        self.backup_database()

        # Initialize the database tables if they are missing
        self._ensure_database_schema()

        # Build dependency graph for all existing skills in database
        try:
            self.build_all_dependencies()
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to build all dependencies: {e}", "WARN")

    def _ensure_database_schema(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA auto_vacuum = INCREMENTAL;")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            skill_name TEXT,
            version INTEGER,
            code TEXT,
            strategy TEXT,
            latency_ms REAL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS banned_strategies (
            skill_name TEXT,
            strategy TEXT,
            cooldown_remaining INTEGER,
            PRIMARY KEY (skill_name, strategy)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_dependencies (
            skill_name TEXT,
            dependency_name TEXT,
            PRIMARY KEY (skill_name, dependency_name)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS anti_patterns (
            skill_name TEXT,
            pattern TEXT,
            occurrences INTEGER,
            PRIMARY KEY (skill_name, pattern)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT,
            function_name TEXT,
            code TEXT,
            backup_path TEXT,
            scheduled_time DATETIME,
            status TEXT DEFAULT 'pending'
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_budgets (
            skill_name TEXT PRIMARY KEY,
            total_tokens INTEGER DEFAULT 0,
            total_calls INTEGER DEFAULT 0
        );
        """)
        
        # Add baseline / hash columns to active_skills if missing
        import sqlite3
        for col, col_type in [("baseline_harness", "TEXT"), ("baseline_latency", "REAL"), ("baseline_memory", "INTEGER"), ("harness_hash", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE active_skills ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass
                
        conn.commit()
        conn.close()

    @property
    def api_key(self) -> str:
        """Dynamically returns the currently active API key from the pool."""
        return self.select_api_key()

    @api_key.setter
    def api_key(self, value: str):
        """Sets the active API key (backwards compatible with tests)."""
        if not self.api_keys:
            self.api_keys = [value]
        else:
            if self.active_key_index < len(self.api_keys):
                self.api_keys[self.active_key_index] = value
            else:
                self.api_keys = [value]
                self.active_key_index = 0
        
        # Ensure stats tracked for this key
        if value not in self.key_stats:
            now_time = time.time()
            self.key_stats[value] = {
                'rpm_minute': [],
                'tpm_minute': 0,
                'daily_tpm': 0,
                'last_reset': now_time,
                'last_tpm_reset': now_time,
                'total_calls': 0
            }

    def select_api_key(self, estimated_tokens: int = 4000) -> str:
        if not self.api_keys:
            return ""
            
        now_time = time.time()
        RPM_LIMIT = 12
        TPM_LIMIT = 200000
        DAILY_TPM_CAP = 1000000
        
        # Refresh reset windows for all keys
        for k in self.api_keys:
            stats = self.key_stats.setdefault(k, {
                'rpm_minute': [],
                'tpm_minute': 0,
                'daily_tpm': 0,
                'last_reset': now_time,
                'last_tpm_reset': now_time,
                'total_calls': 0
            })
            
            # Clean rpm_minute list
            stats['rpm_minute'] = [t for t in stats['rpm_minute'] if now_time - t < 60.0]
            
            # Reset TPM every 60s
            if now_time - stats['last_tpm_reset'] >= 60.0:
                stats['tpm_minute'] = 0
                stats['last_tpm_reset'] = now_time
                
            # Reset daily TPM every 24h
            if now_time - stats['last_reset'] >= 86400.0:
                stats['daily_tpm'] = 0
                stats['last_reset'] = now_time
                
        # Find viable keys
        viable = []
        for k in self.api_keys:
            stats = self.key_stats[k]
            rpm = len(stats['rpm_minute'])
            tpm = stats['tpm_minute']
            
            if rpm < RPM_LIMIT and tpm + estimated_tokens < TPM_LIMIT and stats['daily_tpm'] < DAILY_TPM_CAP:
                # Score by headroom: prefer keys with most quota remaining
                headroom = (RPM_LIMIT - rpm) + (TPM_LIMIT - tpm) / 1000.0
                headroom = max(headroom, 0.001)
                viable.append((k, headroom))
                
        if not viable:
            ExecutionLogger.log("LLM_CLIENT", "All keys exhausted or rate-limited. Sleeping for 10s...", "WARN")
            time.sleep(10.0)
            return self.select_api_key(estimated_tokens)
            
        # Weighted random: prefer high headroom, but allow low headroom
        import random
        total_headroom = sum(h for _, h in viable)
        weights = [h / total_headroom for _, h in viable]
        chosen = random.choices([k for k, _ in viable], weights=weights)[0]
        
        self.active_key_index = self.api_keys.index(chosen)
        return chosen

    def record_usage(self, key: str, tokens: int):
        stats = self.key_stats.get(key)
        if stats:
            stats.setdefault('rpm_minute', []).append(time.time())
            if not isinstance(stats['rpm_minute'], list):
                stats['rpm_minute'] = [time.time()]
            stats['tpm_minute'] = stats.get('tpm_minute', 0) + tokens
            stats['daily_tpm'] = stats.get('daily_tpm', 0) + tokens
            stats['total_calls'] = stats.get('total_calls', 0) + 1
            
            # Log per-key rpm_minute, tpm_minute, daily_tpm after every call
            rpm = len(stats['rpm_minute'])
            tpm = stats['tpm_minute']
            daily = stats['daily_tpm']
            ExecutionLogger.log("LLM_CLIENT", f"API KEY USAGE: Key prefix {key[:8]}... | RPM (minute): {rpm} | TPM (minute): {tpm} | TPM (daily): {daily}", "INFO")

    def record_failure(self, key: str):
        stats = self.key_stats.get(key)
        if stats:
            stats['rpm_minute'] = [time.time()] * 999  # block it until next reset (60s)
            stats['tpm_minute'] = 999999

    def rotate_api_key(self):
        """Swaps to the next available API key in the pool (compatibility fallback)."""
        if len(self.api_keys) > 1:
            old_idx = self.active_key_index
            self.active_key_index = (self.active_key_index + 1) % len(self.api_keys)
            ExecutionLogger.log("LLM_CLIENT", f"API Key Rotation: Swapped active index from {old_idx} to {self.active_key_index}.", "WARN")
        else:
            ExecutionLogger.log("LLM_CLIENT", "API Key Rotation requested but no secondary keys are available in the pool.", "WARN")

    def _get_conn(self):
        # Trigger periodic backup check
        self.check_periodic_backup()
        
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def check_periodic_backup(self):
        if getattr(self, '_is_backing_up', False):
            return
        
        now = time.time()
        last_backup = getattr(self, '_last_backup_time', 0.0)
        if last_backup == 0.0:
            self._last_backup_time = now
            return
            
        # 30 minutes = 1800 seconds
        if now - last_backup >= 1800:
            self._is_backing_up = True
            try:
                self.backup_database()
                self._last_backup_time = now
            finally:
                self._is_backing_up = False

    def verify_database(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            if result and result[0] != 'ok':
                ExecutionLogger.log("DATABASE", f"DATABASE_CORRUPTION: {result[0]}. Restoring from backup...", "CRITICAL")
                self.restore_database_from_backup()
        except sqlite3.DatabaseError as e:
            ExecutionLogger.log("DATABASE", f"DATABASE_ERROR: {e}. Restoring from backup...", "CRITICAL")
            self.restore_database_from_backup()

    def backup_database(self):
        try:
            backup_dir = os.path.dirname(self.db_path)
            backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("hermit_memory_backup_")])
            while len(backups) >= 5:
                try:
                    os.remove(os.path.join(backup_dir, backups.pop(0)))
                except:
                    break
            
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            backup_filename = f"hermit_memory_backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except:
                    pass
            
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(f"VACUUM INTO '{backup_path}'")
            conn.close()
            ExecutionLogger.log("DATABASE", f"Database successfully backed up to: {backup_filename}", "SUCCESS")
        except Exception as e:
            ExecutionLogger.log("DATABASE", f"Failed to backup database: {e}", "WARN")

    def restore_database_from_backup(self):
        try:
            backup_dir = os.path.dirname(self.db_path)
            backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("hermit_memory_backup_")])
            if backups:
                latest_backup = backups[-1]
                latest_path = os.path.join(backup_dir, latest_backup)
                import shutil
                shutil.copy(latest_path, self.db_path)
                ExecutionLogger.log("DATABASE", f"Successfully restored database from: {latest_backup}", "SUCCESS")
            else:
                ExecutionLogger.log("DATABASE", "Restore failed: No backups available.", "ERROR")
        except Exception as e:
            ExecutionLogger.log("DATABASE", f"Failed to restore database: {e}", "ERROR")

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

    def call_gemini_api(self, prompt: str, system_instruction: Optional[str] = None, skill_name: Optional[str] = None) -> Dict[str, Any]:
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

        # Simple token estimation for key selection headroom check
        estimated_tokens = (len(prompt) // 4) + 1000

        for attempt in range(1, max_retries + 1):
            rpd_before, rpm_before, tpm_before = self.get_rolling_telemetry()
            start_time = time.perf_counter()
            current_key = self.select_api_key(estimated_tokens=estimated_tokens)
            try:
                # Initialize the official SDK client inside the loop to ensure clean connection state
                client = genai.Client(api_key=current_key)
                
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
                
                # Record successful key usage
                self.record_usage(current_key, tpm_used)
                
                if skill_name:
                    self.record_skill_usage(skill_name, tpm_used, calls_used=1)
                
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
                
                # Check for quota exhaustion / rate limits to trigger rotation/penalty
                err_msg = str(e).upper()
                is_quota_error = any(kw in err_msg for kw in ["429", "RESOURCE_EXHAUSTED", "QUOTA EXCEEDED", "RESOURCEEXHAUSTED", "RATE LIMIT"])
                if is_quota_error:
                    ExecutionLogger.log("LLM_CLIENT", f"Quota exhaustion or rate limit detected for key at index {self.active_key_index}.", "WARN")
                    self.record_failure(current_key)
                
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

    def extract_skill_dependencies(self, skill_name: str, code: str) -> List[str]:
        # Find all other skill names referenced in the code
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name FROM active_skills WHERE skill_name != ?", (skill_name,))
        other_skills = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        dependencies = []
        import re
        for other in other_skills:
            # Check if the other skill's name is used as a token/word in code
            pattern = r'\b' + re.escape(other) + r'\b'
            if re.search(pattern, code):
                dependencies.append(other)
        return dependencies

    def update_dependencies_for_skill(self, skill_name: str, code: str):
        dependencies = self.extract_skill_dependencies(skill_name, code)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS skill_dependencies (skill_name TEXT, dependency_name TEXT, PRIMARY KEY (skill_name, dependency_name))")
        cursor.execute("DELETE FROM skill_dependencies WHERE skill_name = ?", (skill_name,))
        for dep in dependencies:
            cursor.execute("INSERT OR IGNORE INTO skill_dependencies (skill_name, dependency_name) VALUES (?, ?)", (skill_name, dep))
        conn.commit()
        conn.close()

    def build_all_dependencies(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS skill_dependencies (skill_name TEXT, dependency_name TEXT, PRIMARY KEY (skill_name, dependency_name))")
        cursor.execute("SELECT skill_name, code FROM active_skills")
        rows = cursor.fetchall()
        conn.close()
        for name, code in rows:
            if code:
                self.update_dependencies_for_skill(name, code)

    def get_dependents(self, skill_name: str) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS skill_dependencies (skill_name TEXT, dependency_name TEXT, PRIMARY KEY (skill_name, dependency_name))")
        cursor.execute("SELECT skill_name FROM skill_dependencies WHERE dependency_name = ?", (skill_name,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def register_or_update_skill(self, skill_name: str, description: str, code: str) -> bool:
        """Saves or updates a skill in the active_skills registry table."""
        if skill_name in self.IMMUTABLE_FUNCTIONS:
            ExecutionLogger.log("REGISTRY", f"SKIPPED_IMMUTABLE: Cannot register/update immutable function '{skill_name}'.", "WARN")
            return False

        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        
        # Parse verification harness
        harness = DEFAULT_HARNESS
        if "=== HARNESS ===" in description:
            parts = description.split("=== HARNESS ===")
            harness = parts[1].strip()
            
        import hashlib
        harness_hash = hashlib.sha256(harness.encode("utf-8")).hexdigest()[:16]
        
        if row:
            version = row[0] + 1
            # Retrieve existing baseline to make sure we don't overwrite it
            cursor.execute("SELECT baseline_harness, harness_hash, baseline_latency, baseline_memory FROM active_skills WHERE skill_name = ?", (skill_name,))
            base_row = cursor.fetchone()
            if base_row and base_row[0]:
                b_harness, b_hash, b_lat, b_mem = base_row
            else:
                b_harness, b_hash, b_lat, b_mem = harness, harness_hash, None, None
                
            cursor.execute("""
                UPDATE active_skills 
                SET description = ?, code = ?, version = ?, timestamp = CURRENT_TIMESTAMP,
                    baseline_harness = ?, harness_hash = ?, baseline_latency = ?, baseline_memory = ?
                WHERE skill_name = ?
            """, (description, code, version, b_harness, b_hash, b_lat, b_mem, skill_name))
            action = "updated"
        else:
            version = 1
            cursor.execute("""
                INSERT INTO active_skills (skill_name, description, code, version, baseline_harness, harness_hash)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (skill_name, description, code, harness, harness_hash))
            action = "registered"
            
        conn.commit()
        conn.close()
        
        # Build dependency graph
        try:
            self.update_dependencies_for_skill(skill_name, code)
        except Exception as e:
            ExecutionLogger.log("REGISTRY", f"Failed to update dependencies for skill '{skill_name}': {e}", "WARN")

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
                
                # Keep backup file
                import datetime
                timestamp_str = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S')
                final_backup_path = f"{target_file}.hermit_backup_v{timestamp_str}"
                shutil.copy2(backup_path, final_backup_path)
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    
                # Schedule validation re-run in 1 hour (60 minutes)
                scheduled_dt = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=60)
                scheduled_time_str = scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')
                
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scheduled_validations (file_path, function_name, code, backup_path, scheduled_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (target_file, skill_name, optimized_code, final_backup_path, scheduled_time_str))
                conn.commit()
                conn.close()
                
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

    def process_scheduled_validations(self) -> List[str]:
        """Runs delayed validations for self-patches and rolls back if tests fail."""
        import datetime
        import subprocess
        import shutil
        import sys
        
        conn = self._get_conn()
        cursor = conn.cursor()
        now_str = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            SELECT id, file_path, function_name, code, backup_path 
            FROM scheduled_validations 
            WHERE status = 'pending' AND scheduled_time <= ?
        """, (now_str,))
        validations = cursor.fetchall()
        conn.close()
        
        results = []
        for val_id, file_path, func_name, code, backup_path in validations:
            ExecutionLogger.log("INTROSPECTION", f"Running scheduled validation for '{func_name}' in '{file_path}'...", "INFO")
            
            # Run unit tests
            self_dir = os.path.dirname(os.path.abspath(__file__))
            test_res = subprocess.run(
                [sys.executable, "test_hermit.py"],
                capture_output=True,
                text=True,
                cwd=self_dir
            )
            
            status = 'passed'
            if test_res.returncode != 0:
                ExecutionLogger.log("INTROSPECTION", f"PATCH_REVERTED: Scheduled validation failed for '{func_name}'. Restoring backup from '{backup_path}'...", "ERROR")
                write_thought_ledger("INTROSPECTION_PATCH_REVERT", f"Scheduled validation failed for '{func_name}'", f"Restoring from backup.\nExit Code: {test_res.returncode}\nStderr:\n{test_res.stderr}")
                
                # Restore backup
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, file_path)
                    status = 'reverted'
                else:
                    ExecutionLogger.log("INTROSPECTION", f"Backup file '{backup_path}' not found! Cannot revert.", "ERROR")
                    status = 'failed_backup_missing'
            else:
                ExecutionLogger.log("INTROSPECTION", f"Scheduled validation passed for '{func_name}'. Keeping patch.", "SUCCESS")
                
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE scheduled_validations SET status = ? WHERE id = ?", (status, val_id))
            conn.commit()
            conn.close()
            results.append(f"{func_name}: {status}")
            
        return results

    def detect_oscillation(self, skill_name: str, window: int = 6) -> Tuple[bool, List[str]]:
        """Detects if optimization strategies are oscillating (A-B-A-B or A-B-C-A-B-C)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT strategy FROM version_history 
            WHERE skill_name = ? 
            ORDER BY timestamp DESC LIMIT ?
        """, (skill_name, window))
        strategies = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        strategies.reverse()
        
        if len(strategies) < 4:
            return False, []
            
        # Check for period-2 cycles: A-B-A-B
        # Check for period-3 cycles: A-B-C-A-B-C
        for period in [2, 3]:
            if len(strategies) >= period * 2:
                first = strategies[-period*2:-period]
                second = strategies[-period:]
                if first == second:
                    return True, list(set(first))
                    
        # Check for return-after-short-exploration: A at vN, B at vN+1, A at vN+2
        if len(strategies) >= 3:
            if strategies[-1] == strategies[-3] and strategies[-2] != strategies[-1]:
                # Only ban if this exact flip happened before in window
                flips = []
                for i in range(len(strategies) - 2):
                    if strategies[i] == strategies[i+2] != strategies[i+1]:
                        flips.append((strategies[i], strategies[i+1], strategies[i+2]))
                if len(flips) >= 2:
                    return True, [strategies[-1], strategies[-2]]
                    
        return False, []

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

        res = self.call_gemini_api(prompt, system_instruction, skill_name=skill_name)
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
                                    if node.name in self.EXCLUDED_SKILLS or node.name in self.IMMUTABLE_FUNCTIONS:
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

    def ban_strategies(self, skill_name: str, strategies: List[str], cooldown: int = 5):
        res = self.detect_oscillation(skill_name, window=6)
        if isinstance(res, tuple):
            is_cycle, to_ban = res
        else:
            is_cycle = res
            to_ban = strategies
            
        if not is_cycle:
            return
            
        to_ban = to_ban or strategies
            
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banned_strategies (
                skill_name TEXT,
                strategy TEXT,
                cooldown_remaining INTEGER,
                PRIMARY KEY (skill_name, strategy)
            );
        """)
        for strat in to_ban:
            cursor.execute("""
                INSERT OR REPLACE INTO banned_strategies (skill_name, strategy, cooldown_remaining)
                VALUES (?, ?, ?)
            """, (skill_name, strat, cooldown))
        conn.commit()
        conn.close()

    def get_banned_strategies(self, skill_name: str) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='banned_strategies'")
        if not cursor.fetchone():
            conn.close()
            return []
        cursor.execute("SELECT strategy FROM banned_strategies WHERE skill_name = ? AND cooldown_remaining > 0", (skill_name,))
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def decrement_banned_cooldowns(self, skill_name: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='banned_strategies'")
        if not cursor.fetchone():
            conn.close()
            return
        cursor.execute("""
            UPDATE banned_strategies 
            SET cooldown_remaining = cooldown_remaining - 1 
            WHERE skill_name = ?
        """, (skill_name,))
        cursor.execute("""
            DELETE FROM banned_strategies 
            WHERE skill_name = ? AND cooldown_remaining <= 0
        """, (skill_name,))
        conn.commit()
        conn.close()

    def store_version(self, skill_name: str, candidate: Dict[str, Any]):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        version = row[0] if row else 1
        
        cursor.execute("""
            INSERT INTO version_history (skill_name, version, code, strategy, latency_ms)
            VALUES (?, ?, ?, ?, ?)
        """, (skill_name, version, candidate["code"], candidate["branch_name"], candidate["latency"]))
        conn.commit()
        conn.close()

    SKILL_CLASSES = {
        'parser': {
            'strategies': ['regex_compilation', 'dispatch_table', 'short_circuit'],
            'weights': {'latency': 10.0, 'memory': 3.0, 'complexity': 1.0},
            'max_versions': 50
        },
        'search': {
            'strategies': ['memoryview', 'native_find', 'bitmap_index'],
            'weights': {'latency': 10.0, 'memory': 10.0, 'complexity': 0.5},
            'max_versions': 100
        },
        'io_bound': {
            'strategies': ['async_io', 'buffer_pool', 'mmap'],
            'weights': {'latency': 5.0, 'memory': 2.0, 'complexity': 1.0},
            'max_versions': 20
        },
        'general': {
            'strategies': [],
            'weights': {'latency': 10.0, 'memory': 2.0, 'complexity': 0.5},
            'max_versions': 50
        }
    }

    def classify_skill(self, skill_name: str, code: str) -> str:
        code_lower = code.lower()
        name_lower = skill_name.lower()
        if 're.' in code or 'parse' in name_lower or 'regex' in name_lower:
            return 'parser'
        if 'find' in name_lower or 'search' in name_lower or 'bitmap' in name_lower or 'index' in name_lower:
            return 'search'
        if 'open(' in code or 'read(' in code or 'write(' in code or 'async' in code:
            return 'io_bound'
        return 'general'

    def calculate_weighted_score(self, skill_name: str, code: str, latency_ms: float, memory_kb: float, complexity: int, baseline: Dict[str, Any] = None) -> float:
        cls = self.classify_skill(skill_name, code)
        weights = self.SKILL_CLASSES[cls]['weights']
        
        if baseline is None:
            return weights['latency'] + weights['memory'] + weights['complexity']
            
        base_lat = baseline['latency'] if baseline['latency'] > 0 else 1.0
        base_mem = baseline['rss'] if baseline['rss'] > 0 else 1.0
        base_comp = baseline['complexity'] if baseline['complexity'] > 0 else 1.0
        
        latency_ratio = latency_ms / base_lat
        memory_ratio = memory_kb / base_mem
        complexity_ratio = complexity / base_comp
        
        score = (latency_ratio * weights['latency'] +
                 memory_ratio * weights['memory'] +
                 complexity_ratio * weights['complexity'])
        return score

    def pareto_dominates(self, candidate: Dict[str, Any], baseline: Dict[str, Any]) -> Tuple[bool, str]:
        # Gate 1: Latency must improve or stay within noise (5%)
        if candidate['latency'] > baseline['latency'] * 1.05:
            return False, "latency_regression"
            
        # Gate 2: Memory must not regress beyond 10%
        if candidate['rss'] > baseline['rss'] * 1.10:
            return False, "memory_regression"
            
        # Gate 3: At least one dimension must improve significantly (>5%)
        latency_improved = candidate['latency'] < baseline['latency'] * 0.95
        memory_improved = candidate['rss'] < baseline['rss'] * 0.95
        complexity_improved = candidate['complexity'] < baseline['complexity'] * 0.95
        
        if not any([latency_improved, memory_improved, complexity_improved]):
            return False, "insignificant_improvement"
            
        return True, "accepted"

    def detect_measurement_anomaly(self, skill_name: str, code: str, avg_rss: float) -> bool:
        code_lower = code.lower()
        has_allocations = any(x in code_lower for x in ['list', 'dict', 'set', 'bytearray', 'bytes', '[0]*', 'range', 'open', 'read'])
        if has_allocations and avg_rss < 1.0:
            return True
        return False

    def get_skill_budget_stats(self, skill_name: str) -> Dict[str, int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT total_tokens, total_calls FROM skill_budgets WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"total_tokens": row[0], "total_calls": row[1]}
        return {"total_tokens": 0, "total_calls": 0}

    def record_skill_usage(self, skill_name: str, tokens_used: int, calls_used: int = 1):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO skill_budgets (skill_name, total_tokens, total_calls)
            VALUES (?, ?, ?)
            ON CONFLICT(skill_name) DO UPDATE SET
                total_tokens = total_tokens + excluded.total_tokens,
                total_calls = total_calls + excluded.total_calls
        """, (skill_name, tokens_used, calls_used))
        conn.commit()
        conn.close()

    def can_attempt_skill(self, skill_name: str) -> bool:
        max_tokens_per_skill = 500000
        max_calls_per_skill = 100
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        merges = (row[0] - 1) if row else 0
        conn.close()
        
        stats = self.get_skill_budget_stats(skill_name)
        if stats['total_tokens'] > max_tokens_per_skill and merges <= 10:
            ExecutionLogger.log("BUDGET_GATE", f"BUDGET_EXHAUSTED: '{skill_name}' has used {stats['total_tokens']} tokens (> {max_tokens_per_skill}). Gating out further optimization.", "WARN")
            return False
            
        if stats['total_calls'] > max_calls_per_skill:
            ExecutionLogger.log("BUDGET_GATE", f"CALL_BUDGET_EXHAUSTED: '{skill_name}' has reached {stats['total_calls']} calls limit.", "WARN")
            return False
            
        return True

    def is_significant_improvement(self, baseline_latencies: List[float], candidate_latencies: List[float]) -> bool:
        import math
        n1 = len(baseline_latencies)
        n2 = len(candidate_latencies)
        if n1 < 2 or n2 < 2:
            return sum(candidate_latencies)/n2 < sum(baseline_latencies)/n1
            
        mean1 = sum(baseline_latencies) / n1
        mean2 = sum(candidate_latencies) / n2
        
        if mean2 >= mean1:
            return False
            
        var1 = sum((x - mean1) ** 2 for x in baseline_latencies) / (n1 - 1)
        var2 = sum((x - mean2) ** 2 for x in candidate_latencies) / (n2 - 1)
        
        pooled_se = math.sqrt(var1/n1 + var2/n2)
        if pooled_se == 0:
            return True
            
        t_stat = (mean1 - mean2) / pooled_se
        df = n1 + n2 - 2
        
        t_table = {
            2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015,
            6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833,
            10: 1.812, 12: 1.782, 15: 1.753, 20: 1.725
        }
        crit_t = t_table.get(df, 1.86)
        return t_stat > crit_t

    def update_anti_patterns(self, skill_name: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anti_patterns (
                skill_name TEXT,
                pattern TEXT,
                occurrences INTEGER,
                PRIMARY KEY (skill_name, pattern)
            );
        """)
        cursor.execute("""
            SELECT stderr FROM reality_tests 
            WHERE script_name LIKE ? AND status = 'FAIL' AND stderr IS NOT NULL
        """, (f"%{skill_name}%",))
        rows = cursor.fetchall()
        
        error_counts = {}
        for row in rows:
            stderr = row[0].strip()
            if not stderr:
                continue
            lines = [line.strip() for line in stderr.split('\n') if line.strip()]
            if lines:
                last_line = lines[-1]
                if ":" in last_line and "traceback" not in last_line.lower():
                    error_counts[last_line] = error_counts.get(last_line, 0) + 1
                    
        for err, count in error_counts.items():
            cursor.execute("""
                INSERT OR REPLACE INTO anti_patterns (skill_name, pattern, occurrences)
                VALUES (?, ?, ?)
            """, (skill_name, err, count))
            
        conn.commit()
        conn.close()

    def get_anti_patterns(self, skill_name: str) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anti_patterns (
                skill_name TEXT,
                pattern TEXT,
                occurrences INTEGER,
                PRIMARY KEY (skill_name, pattern)
            );
        """)
        cursor.execute("""
            SELECT pattern FROM anti_patterns 
            WHERE skill_name = ? AND occurrences >= 3
        """, (skill_name,))
        local_patterns = [r[0] for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT pattern FROM anti_patterns 
            WHERE occurrences >= 10
        """)
        global_patterns = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        unique_patterns = list(set(local_patterns + global_patterns))
        anti_instructions = []
        for p in unique_patterns:
            if "AttributeError" in p and "memoryview" in p and "find" in p:
                anti_instructions.append("DO NOT use .find() on memoryview objects. Convert memoryview to bytes/bytearray first, or use bytes.find() / manual indexing.")
            elif "NameError" in p:
                anti_instructions.append(f"Avoid NameErrors. Ensure all referenced variables, functions, and modules are defined/imported. (Error: {p})")
            elif "TypeError" in p:
                anti_instructions.append(f"Ensure type compatibility. Verify function arguments and slice objects are of the correct types. (Error: {p})")
            else:
                anti_instructions.append(f"Avoid code mutations that trigger: {p}")
                
        return anti_instructions

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
        # Decrement banned strategy cooldowns for this skill
        self.decrement_banned_cooldowns(skill_name)

        skill_info = self.get_skill(skill_name)
        if not skill_info:
            err = f"Skill '{skill_name}' is not registered."
            ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
            write_thought_ledger("EVOLUTION_FAILED", "Initialization error", f"Skill '{skill_name}' is not registered in active_skills.")
            return False, err

        desc, base_code, version = skill_info
        ExecutionLogger.log("ORCHESTRATOR", f"Initializing Evolutionary Pipeline for: {skill_name} (v{version})")

        # Check frozen harness and drift
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT baseline_harness, harness_hash, baseline_latency, baseline_memory FROM active_skills WHERE skill_name = ?", (skill_name,))
        row = cursor.fetchone()
        conn.close()
        
        use_harness = verification_harness
        if row and row[0] is not None and row[2] is not None:
            frozen_harness, frozen_hash, base_lat, base_mem = row
            # Compare hash of passed harness with frozen hash
            import hashlib
            passed_hash = hashlib.sha256(verification_harness.encode("utf-8")).hexdigest()[:16]
            if passed_hash != frozen_hash:
                err = f"HARNESS_DRIFT_ERROR: Verification harness for '{skill_name}' hash {passed_hash} != frozen hash {frozen_hash}"
                ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
                write_thought_ledger("HARNESS_DRIFT_ERROR", f"Harness drift detected for '{skill_name}'", err)
                return False, err
            use_harness = frozen_harness
        else:
            # First time running or baseline harness/latency not set. Store the current verification_harness.
            import hashlib
            frozen_hash = hashlib.sha256(verification_harness.encode("utf-8")).hexdigest()[:16]
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE active_skills 
                SET baseline_harness = ?, harness_hash = ?
                WHERE skill_name = ?
            """, (verification_harness, frozen_hash, skill_name))
            conn.commit()
            conn.close()

        # 1. Run baseline in sandbox
        baseline_script = f"{base_code}\n\n{use_harness}"
        baseline_result = run_in_sandbox(baseline_script, "baseline_verify.py")
        baseline_result.log_to_db(self.db_path)

        if baseline_result.exit_code != 0:
            err = f"Baseline failed verification! Stderr: {baseline_result.stderr}"
            ExecutionLogger.log("ORCHESTRATOR", err, "ERROR")
            write_thought_ledger("EVOLUTION_FAILED", "Baseline verification failure", f"Baseline script failed verification in sandbox.\nExit Code: {baseline_result.exit_code}\nStderr:\n{baseline_result.stderr}")
            return False, err

        baseline_complexity = len(base_code)
        ExecutionLogger.log("ORCHESTRATOR", f"Baseline performance: Latency = {baseline_result.duration_ms:.2f} ms | RAM = {baseline_result.max_rss_kb} KB | Complexity = {baseline_complexity} chars", "SUCCESS")

        # Collect baseline latencies (5 runs)
        baseline_latencies = [baseline_result.duration_ms]
        for i in range(4):
            res_base = run_in_sandbox(baseline_script, f"baseline_verify_{i}.py")
            if res_base.exit_code == 0:
                baseline_latencies.append(res_base.duration_ms)

        avg_latency = sum(baseline_latencies) / len(baseline_latencies)
        avg_memory = baseline_result.max_rss_kb

        # Store baseline stats if not already stored
        if row and (row[2] is None or row[3] is None):
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE active_skills 
                SET baseline_latency = ?, baseline_memory = ?
                WHERE skill_name = ?
            """, (avg_latency, avg_memory, skill_name))
            conn.commit()
            conn.close()

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
        skill_class = self.classify_skill(skill_name, base_code)
        class_info = self.SKILL_CLASSES[skill_class]
        strategies_list = class_info['strategies']
        weights_info = class_info['weights']

        system_instruction = (
            "You are Project Hermit's Evolutionary Synthesizer Agent.\n"
            "Your task is to generate three distinct Python code mutation variants to optimize the skill code.\n"
            f"This skill is categorized as a '{skill_class}' task. Optimize it accordingly.\n"
            f"Evaluation criteria prioritizes: Latency (weight: {weights_info['latency']}), Memory (weight: {weights_info['memory']}), Complexity (weight: {weights_info['complexity']}).\n"
            "You must return your output ONLY as a valid JSON object matching the requested schema."
        )
        if strategies_list:
            system_instruction += f"\nSpecifically consider using these strategies: {', '.join(strategies_list)}."

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

        # Retrieve research strategy guide if it exists in skill_research_notes
        research_note_str = ""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='skill_research_notes'")
            if cursor.fetchone():
                cursor.execute("SELECT notes FROM skill_research_notes WHERE skill_name = ?", (skill_name,))
                row = cursor.fetchone()
                if row:
                    research_note_str = f"\nRESEARCH STRATEGY GUIDE & ARCHITECTURAL DIRECTIVES (META-OPTIMIZER OVERRIDE):\n{row[0]}\n"
            conn.close()
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to retrieve research note: {e}", "WARN")

        # Banned strategies check
        banned_strats = self.get_banned_strategies(skill_name)
        banned_str_prompt = ""
        if banned_strats:
            banned_str_prompt = f"\n[PERMANENT CONSTRAINTS - BANNED STRATEGIES (OSCILLATION PREVENTION)]\nDO NOT propose or use any variants using the following banned strategies: {', '.join(banned_strats)}\n"

        # Anti-patterns check
        anti_patterns = self.get_anti_patterns(skill_name)
        anti_str_prompt = ""
        if anti_patterns:
            anti_str_prompt = f"\n[PERMANENT CONSTRAINTS - ANTI-PATTERNS TO AVOID]\n" + "\n".join(f"- {ap}" for ap in anti_patterns) + "\n"

        prompt = f"""
        Generate three distinct optimization variants for the Python skill named '{skill_name}'.
        {user_instruction_str}
        {research_note_str}
        {banned_str_prompt}
        {anti_str_prompt}
        DESCRIPTION:
        {desc}

        BASELINE CODE:
        ```python
        {base_code}
        ```

        VERIFICATION HARNESS:
        ```python
        {use_harness}
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
        res = self.call_gemini_api(prompt, system_instruction, skill_name=skill_name)
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
        baseline_base = {
            "latency": baseline_result.duration_ms,
            "rss": baseline_result.max_rss_kb,
            "complexity": baseline_complexity
        }
        baseline_score = self.calculate_weighted_score(
            skill_name,
            base_code,
            baseline_result.duration_ms,
            baseline_result.max_rss_kb,
            baseline_complexity,
            baseline=None
        )
        ExecutionLogger.log("ORCHESTRATOR", f"Evaluating {len(variants)} generated branch mutations...")

        for var in variants:
            branch_name = var["branch_name"]
            code = var["code"]
            rationale = var["rationale"]
            
            # Check if this strategy is banned
            if branch_name in banned_strats:
                ExecutionLogger.log("ORCHESTRATOR", f"Skipping variant '{branch_name}' (currently banned under oscillation cooldown).", "WARN")
                continue

            ExecutionLogger.log("ORCHESTRATOR", f"Testing branch variant '{branch_name}': {rationale}")
            
            # Combine optimized code + verification harness + current + all historical adversarial checks
            full_test_script = f"{code}\n\n{use_harness}"
            for idx, hist_code in enumerate(historical_tests):
                full_test_script += f"\n\n# --- Historical Test Case {idx+1} ---\n{hist_code}"

            # AST Pre-check
            try:
                import ast
                ast.parse(full_test_script)
            except SyntaxError as err:
                ExecutionLogger.log("ORCHESTRATOR", f"Branch '{branch_name}' failed AST parse check: {err}", "ERROR")
                continue

            # Run in sandbox 5 times to measure latency accurately and test stability
            candidate_latencies = []
            results = []
            for i in range(5):
                res = run_in_sandbox(full_test_script, f"{branch_name}_verify_{i}.py")
                res.log_to_db(self.db_path)
                results.append(res)
                if res.exit_code == 0:
                    candidate_latencies.append(res.duration_ms)

            any_failed = any(r.exit_code != 0 for r in results)
            complexity = len(code)
            
            if not any_failed and candidate_latencies:
                # Average latency and memory
                avg_latency = sum(candidate_latencies) / len(candidate_latencies)
                avg_rss = sum(r.max_rss_kb for r in results) / len(results)
                
                score = self.calculate_weighted_score(
                    skill_name,
                    code,
                    avg_latency,
                    avg_rss,
                    complexity,
                    baseline=baseline_base
                )
                
                # Check Pareto Dominance
                candidate = {
                    "latency": avg_latency,
                    "rss": avg_rss,
                    "complexity": complexity
                }
                is_improved, reason = self.pareto_dominates(candidate, baseline_base)
                
                # Check Measurement Anomaly
                if self.detect_measurement_anomaly(skill_name, code, avg_rss):
                    ExecutionLogger.log("ORCHESTRATOR", f"MEASUREMENT_ANOMALY detected for '{branch_name}': RSS is {avg_rss:.2f} KB (expected > 1.0 KB for buffer allocation). Rejecting variant.", "ERROR")
                    is_improved = False
                    reason = "measurement_anomaly"
                
                if is_improved:
                    # Run downstream verification (regression testing)
                    downstream = self.get_dependents(skill_name)
                    downstream_passed = True
                    for dep in downstream:
                        dep_info = self.get_skill(dep)
                        if not dep_info:
                            continue
                        dep_desc, dep_code, dep_version = dep_info
                        
                        dep_harness = DEFAULT_HARNESS
                        if "=== HARNESS ===" in dep_desc:
                            parts = dep_desc.split("=== HARNESS ===")
                            dep_harness = parts[1].strip()
                            
                        dep_historical = self.get_historical_adversarial_tests(dep)
                        
                        # Downstream regression script
                        downstream_script = f"{code}\n\n{dep_code}\n\n{dep_harness}"
                        for idx, hist_code in enumerate(dep_historical):
                            downstream_script += f"\n\n# --- Historical Test Case {idx+1} ---\n{hist_code}"
                            
                        # Run in sandbox
                        dep_res = run_in_sandbox(downstream_script, f"{branch_name}_downstream_regression_{dep}.py")
                        dep_res.log_to_db(self.db_path)
                        
                        if dep_res.exit_code != 0:
                            ExecutionLogger.log("ORCHESTRATOR", f"REGRESSION: Downstream skill '{dep}' broken by '{branch_name}' mutation.", "ERROR")
                            downstream_passed = False
                            break
                            
                    if downstream_passed:
                        valid_candidates.append({
                            "branch_name": branch_name,
                            "code": code,
                            "latency": avg_latency,
                            "rss": avg_rss,
                            "complexity": complexity,
                            "score": score
                        })
                        self.save_branch_variant(skill_name, branch_name, code, avg_latency, avg_rss, complexity, "candidate")
                        ExecutionLogger.log("ORCHESTRATOR", f"Branch '{branch_name}' PASSED all tests (including downstream) and is Pareto-efficient.", "SUCCESS")
                    else:
                        self.save_branch_variant(skill_name, branch_name, code, avg_latency, avg_rss, complexity, "rejected")
                else:
                    self.save_branch_variant(skill_name, branch_name, code, avg_latency, avg_rss, complexity, "rejected")
                    ExecutionLogger.log("ORCHESTRATOR", f"Branch '{branch_name}' PASSED but failed to optimize metrics significantly.", "WARN")
            else:
                fail_res = [r for r in results if r.exit_code != 0][0] if results else None
                stderr_msg = fail_res.stderr if fail_res else "Unknown execution error"
                self.save_branch_variant(skill_name, branch_name, code, 0.0, 0, complexity, "rejected")
                ExecutionLogger.log("QA_AGENT", f"Branch '{branch_name}' REJECTED: Failed adversarial QA tests. Stderr: {stderr_msg}", "ERROR")

            # Log evaluation details to thoughts ledger
            eval_details = (
                f"Branch: {branch_name}\n"
                f"Latency values: {candidate_latencies}\n"
                f"Complexity: {complexity} chars\n"
                f"Is Improved: {is_improved if (not any_failed and candidate_latencies) else 'N/A'}\n"
            )
            write_thought_ledger("VARIANT_EVALUATION", f"Evaluated variant '{branch_name}'", eval_details)

        # Update persistent anti-patterns based on all recent failures
        try:
            self.update_anti_patterns(skill_name)
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to update anti-patterns: {e}", "WARN")

        # 5. Select the best branch and merge
        if not valid_candidates:
            msg = "INTEGRATION REJECTED: No variants passed all adversarial tests, downstream verification, and optimized metrics."
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
        
        # Store in version history before active skills update
        try:
            self.store_version(skill_name, best)
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to store version history: {e}", "WARN")

        # Check for oscillation/cycling strategies in recent merges
        try:
            is_cycle, to_ban = self.detect_oscillation(skill_name, window=6)
            if is_cycle:
                self.ban_strategies(skill_name, to_ban, cooldown=5)
                ExecutionLogger.log("ORCHESTRATOR", f"OSCILLATION_DETECTED for '{skill_name}': Banned strategies {to_ban} for next 5 attempts.", "WARN")
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Failed to check/apply strategy oscillation bans: {e}", "WARN")

        # Harness drift validation check (re-run v1 code against use_harness to compare with baseline_latency)
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM version_history WHERE skill_name = ? AND version = 1", (skill_name,))
            v1_row = cursor.fetchone()
            
            # If version history does not have v1 (e.g. first optimization run), we can use the baseline code we ran at the start of this evolution step!
            v1_code = v1_row[0] if v1_row else base_code
            
            # Also select baseline latency
            cursor.execute("SELECT baseline_latency FROM active_skills WHERE skill_name = ?", (skill_name,))
            lat_row = cursor.fetchone()
            stored_base_lat = lat_row[0] if (lat_row and lat_row[0] is not None) else None
            conn.close()
            
            if stored_base_lat is not None:
                # Re-run v1 code against the frozen harness
                v1_script = f"{v1_code}\n\n{use_harness}"
                v1_latencies = []
                for i in range(3): # run 3 times to get a stable average
                    v1_res = run_in_sandbox(v1_script, f"{skill_name}_harness_drift_check_{i}.py")
                    if v1_res.exit_code == 0:
                        v1_latencies.append(v1_res.duration_ms)
                
                if v1_latencies:
                    current_v1_lat = sum(v1_latencies) / len(v1_latencies)
                    drift_ratio = abs(current_v1_lat - stored_base_lat) / stored_base_lat
                    if drift_ratio > 0.3:
                        err_msg = f"HARNESS_DRIFT_ERROR: Baseline v1 latency changed from {stored_base_lat:.2f}ms to {current_v1_lat:.2f}ms (drift ratio: {drift_ratio:.2%}). Rejecting merge."
                        ExecutionLogger.log("ORCHESTRATOR", err_msg, "ERROR")
                        write_thought_ledger("HARNESS_DRIFT_ERROR", f"Harness drift detected for '{skill_name}'", err_msg)
                        return False, err_msg
        except Exception as e:
            ExecutionLogger.log("ORCHESTRATOR", f"Harness drift check failed with error: {e}", "WARN")

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
    "mutate_qubo_llm", "select_api_key"
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
