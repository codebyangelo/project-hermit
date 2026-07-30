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
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
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

def ensure_tmpfs_mount(sandbox_dir: str):
    # Do not mount if running in a temp directory (like during unit tests)
    if "tmp" in sandbox_dir or "temp" in sandbox_dir:
        return
    
    # Check if already a mountpoint and if it's writable
    is_mount = False
    try:
        res = subprocess.run(["mountpoint", "-q", sandbox_dir])
        is_mount = (res.returncode == 0)
    except:
        pass
        
    if is_mount:
        # Test if it is writable
        test_file = os.path.join(sandbox_dir, "mount_test.txt")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return # Already mounted and writable, all good!
        except:
            # Mount is broken! Force unmount
            try:
                subprocess.run(["umount", "-f", sandbox_dir], stderr=subprocess.DEVNULL)
            except:
                pass
                
    # Try mounting
    try:
        # Re-ensure directory exists
        os.makedirs(sandbox_dir, exist_ok=True)
        # Try to mount as tmpfs 32M
        subprocess.run(["mount", "-t", "tmpfs", "-o", "size=32M", "tmpfs", sandbox_dir], check=True)
        # Test write access
        test_file = os.path.join(sandbox_dir, "mount_test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        ExecutionLogger.log("SANDBOX", f"Successfully mounted tmpfs on {sandbox_dir}", "SUCCESS")
    except Exception as e:
        # If mount fails or is not writable, clean up/unmount and fallback
        try:
            subprocess.run(["umount", "-f", sandbox_dir], stderr=subprocess.DEVNULL)
        except:
            pass
        # Make sure directory is recreated and writable
        os.makedirs(sandbox_dir, exist_ok=True)

import ast

def analyze_code_safety(code: str) -> Tuple[bool, str]:
    """
    Statically analyzes code to block dangerous imports or calls before execution.
    """
    try:
        tree = ast.parse(code)
    except Exception:
        # If it doesn't parse, let the Python interpreter raise the syntax error naturally
        return True, "passed"
        
    dangerous = ['os.system', 'subprocess', 'socket', 'urllib', 'requests']
    for node in ast.walk(tree):
        # Check standard imports (e.g., import os)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in dangerous or any(alias.name.startswith(d + '.') for d in dangerous):
                    return False, f"blocked_import: {alias.name}"
        # Check from-imports (e.g., from os import system)
        if isinstance(node, ast.ImportFrom):
            if node.module in dangerous or any(node.module.startswith(d + '.') for d in dangerous):
                return False, f"blocked_import: {node.module}"
        # Check calls (e.g., os.system(), eval())
        if isinstance(node, ast.Call):
            # Check attribute calls (e.g., os.system)
            if isinstance(node.func, ast.Attribute):
                func_name = ""
                if isinstance(node.func.value, ast.Name):
                    func_name = f"{node.func.value.id}.{node.func.attr}"
                else:
                    func_name = node.func.attr
                if func_name in ['os.system', 'subprocess.Popen', 'subprocess.run', 'subprocess.call']:
                    return False, f"blocked_call: {func_name}"
                if node.func.attr in ['system', 'popen', 'call']:
                    return False, f"blocked_call: {node.func.attr}"
            # Check direct name calls (e.g., system(), popen())
            elif isinstance(node.func, ast.Name):
                if node.func.id in ['system', 'popen', 'call']:
                    return False, f"blocked_call: {node.func.id}"
                    
    return True, "passed"

def set_sandbox_limits():
    # 512MB virtual memory plus parent's current VmSize to support huge emulation virtual spaces (e.g. Android PRoot)
    vmsize = 0
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmSize:'):
                    vmsize = int(line.split()[1]) * 1024
                    break
    except:
        pass
    if vmsize == 0:
        vmsize = 12 * 1024 * 1024 * 1024 # 12GB fallback
    limit = vmsize + (512 * 1024 * 1024)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except:
        pass
    # 30 second CPU time
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    except:
        pass

def run_in_sandbox(script_content: str, script_name: str = "mutation_test.py", 
                   input_data: str = "", timeout_sec: float = 10.0, 
                   cwd: str = None) -> SandboxResult:
    """
    Executes a script inside an isolated sandbox subprocess.
    Measures execution time and peak memory consumption (RSS) via a fork child's RU_CHILDREN.
    """
    if cwd is None:
        cwd = os.path.dirname(os.path.abspath(__file__))
    
    sandbox_dir = os.path.join(cwd, "sandbox_run")
    os.makedirs(sandbox_dir, exist_ok=True)
    ensure_tmpfs_mount(sandbox_dir)
    
    if script_name.endswith(".py"):
        safe, reason = analyze_code_safety(script_content)
        if not safe:
            ExecutionLogger.log("SANDBOX", f"[SECURITY BLOCKED] Code safety check failed for '{script_name}': {reason}", "ERROR")
            return SandboxResult(
                script_name=script_name,
                script_content=script_content,
                input_data=input_data,
                stdout="",
                stderr=f"[SANDBOX SECURITY ERROR] {reason}",
                exit_code=-3,
                duration_ms=0.0,
                max_rss_kb=0
            )

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
    
    # We use a fork+pipe pattern to get independent child rusage.
    # This completely avoids cumulative high water mark issues of getrusage(RUSAGE_CHILDREN).
    r_pipe, w_pipe = os.pipe()
    start_time = time.perf_counter()
    
    pid = os.fork()
    if pid == 0:
        # Child process: runs the sandbox command, waits for it, and returns the result json.
        os.close(r_pipe)
        try:
            # We run subprocess.run here
            proc = subprocess.run(
                cmd,
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
                cwd=sandbox_dir,
                preexec_fn=set_sandbox_limits
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
        duration_ms = (end_time - start_time) * 1000.0
        
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        max_rss_kb = usage.ru_maxrss
        
        result_dict = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "max_rss_kb": max_rss_kb
        }
        
        os.write(w_pipe, json.dumps(result_dict).encode())
        os.close(w_pipe)
        os._exit(0)
    else:
        # Parent process: wait for fork child to complete and read its JSON result.
        os.close(w_pipe)
        os.waitpid(pid, 0)
        
        data = b""
        while True:
            chunk = os.read(r_pipe, 4096)
            if not chunk:
                break
            data += chunk
        os.close(r_pipe)
        
        # Clean up script file
        try:
            os.remove(script_path)
        except OSError:
            pass
            
        try:
            result_dict = json.loads(data.decode())
            stdout = result_dict["stdout"]
            stderr = result_dict["stderr"]
            exit_code = result_dict["exit_code"]
            duration_ms = result_dict["duration_ms"]
            max_rss_kb = result_dict["max_rss_kb"]
        except Exception as e:
            stdout = ""
            stderr = f"[SANDBOX SYSTEM ERROR] Failed to decode fork JSON: {str(e)}"
            exit_code = -2
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            max_rss_kb = 0

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
