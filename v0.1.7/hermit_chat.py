import os
import sys
import sqlite3
import datetime
from orchestrator import Orchestrator, DB_PATH
from logger import ExecutionLogger

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def print_help():
    print("\n--- Project Hermit Interactive CLI Commands ---")
    print("  status        - Check background daemon status & heartbeat")
    print("  skills        - List all registered skills in database")
    print("  branches      - View genetic branches & optimization candidates")
    print("  telemetry     - Query API rate limit telemetry (RPD, RPM, TPM)")
    print("  failures      - List details of the last 5 failed reality tests")
    print("  discover      - Manually queue a task to discover a new skill from codebase")
    print("  chat <query>  - Ask LLM to analyze the latest sandbox failure trace")
    print("  help          - Show this help menu")
    print("  exit / quit   - Close the interface")
    print("\n* Any other input is treated as a task injection constraint for the Daemon.")
    print("  (e.g., 'Optimize get_state_hash for 20% less RAM' or 'Speed up pattern matching')\n")

def check_status():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT status, last_updated FROM daemon_status WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        print(f"\n[DAEMON STATUS]: {row[0]} (Last Heartbeat: {row[1]})")
    else:
        print("\n[DAEMON STATUS]: Offline / Not initialized.")

def list_skills():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT skill_name, description, version, timestamp FROM active_skills")
    rows = cursor.fetchall()
    conn.close()
    
    print("\n=== REGISTERED ACTIVE SKILLS ===")
    if not rows:
        print("No skills registered yet.")
    for row in rows:
        print(f"\nSkill: {row[0]} (Version {row[2]})")
        print(f"Registered: {row[3]}")
        print(f"Description: {row[1]}")
    print("=================================")

def list_branches():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT branch_name, latency_ms, max_rss_kb, complexity_score, status, timestamp 
        FROM skill_branches 
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    print("\n=== EVOLUTIONARY GENETIC BRANCHES ===")
    if not rows:
        print("No branch variants generated yet.")
    for row in rows:
        print(f"\nBranch: {row[0]}")
        print(f"  Status       : {row[4].upper()}")
        print(f"  Latency      : {row[1]:.2f} ms" if row[1] > 0 else "  Latency      : N/A")
        print(f"  Memory (RSS) : {row[2]} KB" if row[2] > 0 else "  Memory (RSS) : N/A")
        print(f"  Complexity   : {row[3]} chars")
        print(f"  Timestamp    : {row[5]}")
    print("=====================================")

def show_telemetry(orchestrator):
    rpd, rpm, tpm = orchestrator.get_rolling_telemetry()
    print("\n=== ROLLING API TELEMETRY ===")
    print(f"  Requests Last 24 Hours (RPD) : {rpd}")
    print(f"  Requests Last 60 Seconds (RPM): {rpm} (Ceiling: 15)")
    print(f"  Tokens Last 60 Seconds (TPM)  : {tpm} (Ceiling: 250,000)")
    print("==============================")

def show_failures():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, script_name, exit_code, stderr 
        FROM reality_tests 
        WHERE status = 'FAIL' 
        ORDER BY id DESC LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    
    print("\n=== RECENT SANDBOX FAILURES ===")
    if not rows:
        print("No recent failures recorded.")
    for row in rows:
        print(f"\nFailure ID: {row[0]} ({row[1]})")
        print(f"Script: {row[2]} (Exit Code: {row[3]})")
        print(f"Error Log:\n{row[4]}")
    print("================================")

def run_analytical_chat(orchestrator, query):
    if not orchestrator.has_api_access():
        print("[ERROR]: GEMINI_API_KEY env var is required for Analytical Chat.")
        return
        
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, script_name, script_content, stderr, stdout 
        FROM reality_tests 
        WHERE status = 'FAIL' 
        ORDER BY id DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("\n[INFO]: No failed sandbox runs found to analyze.")
        return
        
    test_id, script_name, content, stderr, stdout = row
    
    prompt = f"""
    The user is asking a question about a failed sandbox run in Project Hermit.
    
    USER QUERY:
    {query}
    
    FAILED RUN DETAILS (ID {test_id}):
    - Script: {script_name}
    - Exit Code: -1
    - Stderr:
    {stderr}
    - Stdout:
    {stdout}
    - Script Source Content:
    {content}
    
    Analyze the crash logs and answer the user query, identifying the bugs and explaining how to fix the code.
    """
    
    print(f"\nQuerying LLM regarding failure ID {test_id}...")
    res = orchestrator.call_gemini_api(prompt, "You are a senior systems debugging assistant.")
    if res["success"]:
        print(f"\n=== LLM DEBUGGING RESPONSE ===\n{res['text'].strip()}\n==============================")
    else:
        print(f"\n[ERROR]: Gemini API call failed: {res['error']}")

def inject_task(prompt):
    conn = get_conn()
    cursor = conn.cursor()
    # 1. Fetch all registered skills to scan for matches in prompt
    cursor.execute("SELECT skill_name FROM active_skills")
    registered_skills = [row[0] for row in cursor.fetchall()]
    
    target_skill = None
    for skill in registered_skills:
        if skill.lower() in prompt.lower():
            target_skill = skill
            break
            
    # 2. Default to the most recently registered skill if none matched
    if not target_skill:
        cursor.execute("SELECT skill_name FROM active_skills ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        target_skill = row[0] if row else "get_state_hash" # fallback
        
    cursor.execute("""
        INSERT INTO user_interventions (prompt, status, target_skill)
        VALUES (?, 'pending', ?)
    """, (prompt, target_skill))
    conn.commit()
    conn.close()
    print(f"\n[SUCCESS]: Optimization task injected for skill '{target_skill}' (Status: pending).")
    print("The background daemon will process it on the next loop cycle.")

def inject_discovery_task():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_interventions (prompt, status, target_skill)
        VALUES ('Discover a new computational bottleneck skill from workspace', 'pending', 'discover')
    """)
    conn.commit()
    conn.close()
    print(f"\n[SUCCESS]: Codebase scanning discovery task injected (Status: pending).")
    print("The background daemon will run codebase discovery on the next loop cycle.")

def main():
    orchestrator = Orchestrator()
    print("====================================================")
    print("      Project Hermit - Decoupled CLI Chat Prompt    ")
    print("====================================================")
    print_help()
    
    while True:
        try:
            inp = input("\nhermit> ").strip()
            if not inp:
                continue
                
            lower_inp = inp.lower()
            
            if lower_inp in ("exit", "quit"):
                print("Exiting CLI. Daemon will continue in background.")
                break
            elif lower_inp == "help":
                print_help()
            elif lower_inp == "status":
                check_status()
            elif lower_inp == "skills":
                list_skills()
            elif lower_inp == "branches":
                list_branches()
            elif lower_inp == "telemetry":
                show_telemetry(orchestrator)
            elif lower_inp == "failures":
                show_failures()
            elif lower_inp == "discover":
                inject_discovery_task()
            elif lower_inp.startswith("chat "):
                query = inp[5:].strip()
                run_analytical_chat(orchestrator, query)
            else:
                inject_task(inp)
                
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI. Daemon will continue in background.")
            break
        except Exception as e:
            print(f"[ERROR]: CLI command error: {e}")

if __name__ == "__main__":
    main()
