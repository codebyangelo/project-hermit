import sqlite3
import os

def init_database(db_path):
    """Initializes the SQLite database with WAL mode and multi-agent tables for Hermit v0.0.3."""
    print(f"Initializing Hermit v0.0.3 database at: {db_path}")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()

    # Table 1: limit_telemetry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS limit_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        rpd INTEGER,
        rpm INTEGER,
        tpm INTEGER,
        error_code TEXT,
        latency_ms INTEGER,
        notes TEXT
    );
    """)

    # Table 2: reality_tests
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
        metrics TEXT,                 -- JSON metrics (RAM, time, complexity)
        status TEXT                   -- PASS or FAIL
    );
    """)

    # Table 3: active_skills
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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daemon_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table 5: user_interventions
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

    # Table 6: skill_branches (Genetic Branching)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skill_branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        skill_name TEXT,
        branch_name TEXT,             -- e.g. "regex_variant", "find_variant"
        code TEXT,
        latency_ms REAL,
        max_rss_kb INTEGER,
        complexity_score INTEGER,     -- character count or line count
        status TEXT                   -- "candidate", "merged", "rejected"
    );
    """)

    # Table 7: adversarial_tests (New in v0.0.3 to prevent regression)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS adversarial_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        skill_name TEXT,
        test_code TEXT
    );
    """)

    # Table 8: skill_research_notes (New in v0.1.5 for meta-optimization)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skill_research_notes (
        skill_name TEXT PRIMARY KEY,
        notes TEXT NOT NULL,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("Hermit v0.0.3 database initialization complete.")

if __name__ == "__main__":
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    db_file_path = os.path.join(workspace_dir, "hermit_memory.db")
    init_database(db_file_path)
