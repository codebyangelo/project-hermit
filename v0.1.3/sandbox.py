import os
import sys
import subprocess
import time
import resource
import json
import sqlite3
from typing import Dict, Any, Tuple
from logger import ExecutionLogger

# Resolve database path relative to this script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")

class SandboxResult:
    """Represents the results of a reality test run inside the sandbox."""
    def __init__(self, script_name: str, script_content: str, input_data: str,
                 stdout: str, stderr: str, exit_code: int, duration_ms: float, max_rss_kb: int):
        self.script_name = script_name
        self.script_content = script_content
        self.input_data = input_data
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_ms = duration_ms
        self.max_rss_kb = max_rss_kb
        self.status = "PASS" if exit_code == 0 else "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "script_name": self.script_name,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "max_rss_kb": self.max_rss_kb,
            "status": self.status
        }

    def log_to_db(self, db_path: str = DB_PATH) -> int:
        """Saves the reality test result into the SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        metrics_json = json.dumps({
            "duration_ms": self.duration_ms,
            "max_rss_kb": self.max_rss_kb
        })

        cursor.execute("""
        INSERT INTO reality_tests (
            script_name, script_content, input_data, stdout, stderr, exit_code, metrics, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.script_name,
            self.script_content,
            self.input_data,
            self.stdout,
            self.stderr,
            self.exit_code,
            metrics_json,
            self.status
        ))
        
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return test_id

def run_in_sandbox(script_content: str, script_name: str = "mutation_test.py", 
                   input_data: str = "", timeout_sec: float = 10.0, 
                   cwd: str = None) -> SandboxResult:
    """
    Executes a script inside an isolated sandbox subprocess.
    Measures execution time and peak memory consumption (RSS).
    """
    if cwd is None:
        cwd = os.path.dirname(os.path.abspath(__file__))
    
    sandbox_dir = os.path.join(cwd, "sandbox_run")
    os.makedirs(sandbox_dir, exist_ok=True)
    
    script_path = os.path.join(sandbox_dir, script_name)
    
    if script_name.endswith(".py"):
        typing_header = "from typing import List, Dict, Tuple, Any, Optional, Set, Union, Callable\n"
        if "from typing import" not in script_content:
            script_content = typing_header + script_content
            
    # Write the script content safely
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
        
    # Prepare execution command
    if script_name.endswith(".py"):
        cmd = [sys.executable, script_path]
    elif script_name.endswith(".sh"):
        cmd = ["bash", script_path]
    else:
        cmd = [script_path]

    ExecutionLogger.log("SANDBOX", f"Executing '{script_name}' inside isolated environment (timeout: {timeout_sec}s)...")
    # Pre-execution rusage to establish child baseline
    usage_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    start_time = time.perf_counter()

    try:
        # Run subprocess with timeout and capture outputs
        proc = subprocess.run(
            cmd,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            cwd=sandbox_dir
        )
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout if e.stdout else ""
        stderr = (e.stderr if e.stderr else "") + f"\n[TIMEOUT] Process exceeded limit of {timeout_sec} seconds."
        exit_code = -1
    except Exception as e:
        stdout = ""
        stderr = f"[SANDBOX ERROR] Failed to run subprocess: {str(e)}"
        exit_code = -2

    end_time = time.perf_counter()
    usage_end = resource.getrusage(resource.RUSAGE_CHILDREN)
    
    # Calculate duration
    duration_ms = (end_time - start_time) * 1000.0
    
    # Calculate max RSS of the children during this run
    # Note: ru_maxrss returns kilobytes on Linux
    max_rss_kb = usage_end.ru_maxrss - usage_start.ru_maxrss
    if max_rss_kb < 0:
        max_rss_kb = usage_end.ru_maxrss # fallback to total child maxrss

    # Clean up script file
    try:
        os.remove(script_path)
    except OSError:
        pass

    log_level = "SUCCESS" if exit_code == 0 else "ERROR"
    ExecutionLogger.log("SANDBOX", f"'{script_name}' execution completed. Exit code: {exit_code}, duration: {duration_ms:.2f} ms, max RSS change: {max_rss_kb} KB", log_level)

    return SandboxResult(
        script_name=script_name,
        script_content=script_content,
        input_data=input_data,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        duration_ms=duration_ms,
        max_rss_kb=max_rss_kb
    )

if __name__ == "__main__":
    # Self-test the sandbox function
    test_script = """
import time
print("Hello from Sandbox!")
# Consume some memory
large_list = [0] * 1000000
time.sleep(0.1)
"""
    print("Testing sandbox execution...")
    res = run_in_sandbox(test_script, "test_rss.py")
    print(f"Exit Code: {res.exit_code}")
    print(f"Stdout: {res.stdout.strip()}")
    print(f"Stderr: {res.stderr.strip()}")
    print(f"Duration: {res.duration_ms:.2f} ms")
    print(f"Max RSS Change: {res.max_rss_kb} KB")
    
    # Test DB insertion
    try:
        test_id = res.log_to_db()
        print(f"Successfully logged to DB under ID: {test_id}")
    except Exception as e:
        print(f"Failed to log to DB: {e}")
