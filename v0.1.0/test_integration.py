import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")

def test_integration():
    print("=== PROJECT HERMIT CONCURRENT INTEGRATION TEST ===")
    
    # 1. Verify connection and WAL mode
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    # Check daemon status
    cursor.execute("SELECT status, last_updated FROM daemon_status WHERE id = 1")
    status_row = cursor.fetchone()
    if status_row:
        print(f"Verified Daemon Status: '{status_row[0]}' (Heartbeat: {status_row[1]})")
    else:
        print("FAIL: Daemon status not initialized. Is daemon running?")
        conn.close()
        return False

    # 2. Inject task into user_interventions
    print("Injecting test intervention: 'Optimize hex_search for latency'...")
    cursor.execute("""
        INSERT INTO user_interventions (prompt, status, target_skill)
        VALUES (?, 'pending', 'hex_search')
    """, ("Optimize hex_search for latency",))
    conn.commit()
    
    task_id = cursor.lastrowid
    print(f"Task injected with ID: {task_id}")
    conn.close()
    
    # 3. Wait for Daemon to poll and process (polling up to 90 seconds)
    print("Polling user_interventions for task status...")
    max_attempts = 30
    status, result = "pending", None
    
    for attempt in range(1, max_attempts + 1):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT status, result FROM user_interventions WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("FAIL: Task not found in database.")
            return False
            
        status, result = row
        print(f"[Attempt {attempt}/{max_attempts}] Task Status: '{status}'")
        
        if status in ("completed", "failed"):
            break
            
        time.sleep(3)
        
    print(f"Final Task Status: '{status}'")
    print(f"Final Task Result: '{result}'")
    
    if status in ("completed", "failed"):
        print("SUCCESS: The background daemon successfully picked up and processed the task!")
        return True
    else:
        print(f"FAIL: Task still in state '{status}'. Daemon might be stuck or slow.")
        return False

if __name__ == "__main__":
    success = test_integration()
    if not success:
        os._exit(1)
