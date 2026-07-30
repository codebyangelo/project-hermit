import sqlite3
import os
import sys

def init_database(db_path):
    """Initializes the SQLite database with the required tables for Project Hermit."""
    print(f"Initializing database at: {db_path}")
    # Use timeout to prevent database locks
    conn = sqlite3.connect(db_path, timeout=10)
    
    # Enable WAL mode for concurrent read/write support
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()

    # Table 1: limit_telemetry
    # Tracks hard/soft API ceilings and performance metrics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS limit_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        rpd INTEGER,                  -- Requests Per Day
        rpm INTEGER,                  -- Requests Per Minute
        tpm INTEGER,                  -- Tokens Per Minute
        error_code TEXT,              -- API error code or status
        latency_ms INTEGER,           -- Round-trip latency in milliseconds
        notes TEXT
    );
    """)

    # Table 2: reality_tests
    # Logs every script simulation, input, output, and validation results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reality_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        script_name TEXT,
        script_content TEXT,
        input_data TEXT,
        stdout TEXT,
        stderr TEXT,
        exit_code INTEGER,
        metrics TEXT,                 -- JSON formatted string tracking RAM usage, tokens, execution time
        status TEXT                   -- PASS or FAIL
    );
    """)

    # Table 3: active_skills
    # A registry of integrated, validated, and optimized code mutations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        skill_name TEXT UNIQUE,
        description TEXT,
        code TEXT,
        version INTEGER DEFAULT 1
    );
    """)

    # Table 4: daemon_status
    # Broadcasts daemon's current state and last heartbeat
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daemon_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table 5: user_interventions
    # Tasks injected by the human user via CLI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt TEXT,
        status TEXT DEFAULT 'pending',
        target_skill TEXT,
        verification_harness TEXT,
        result TEXT
    );
    """)

    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    # Default to placing hermit_memory.db in the same directory as the script
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    db_file_path = os.path.join(workspace_dir, "hermit_memory.db")
    init_database(db_file_path)
