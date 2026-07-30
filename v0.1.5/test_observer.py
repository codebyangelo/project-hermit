import os
import unittest
import tempfile
import sqlite3
from observer import EvolutionObserver

class TestEvolutionObserver(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and test database
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_hermit_observer.db")
        
        # Initialize SQLite schema
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            skill_name TEXT UNIQUE,
            description TEXT,
            code TEXT,
            version INTEGER DEFAULT 1
        );
        """)
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            skill_name TEXT,
            branch_name TEXT,
            code TEXT,
            latency_ms REAL,
            max_rss_kb INTEGER,
            complexity_score INTEGER,
            status TEXT
        );
        """)
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS reality_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            script_name TEXT,
            script_content TEXT,
            input_data TEXT,
            stdout TEXT,
            stderr TEXT,
            exit_code INTEGER,
            metrics TEXT,
            status TEXT
        );
        """)
        
        self.cursor.execute("""
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
        
        # Insert mock active skill
        self.cursor.execute(
            "INSERT INTO active_skills (skill_name, description, code, version) VALUES (?, ?, ?, ?)",
            ("test_skill", "A test skill description", "def test_skill():\n    return 42", 2)
        )
        
        # Insert mock branch variants
        self.cursor.execute(
            "INSERT INTO skill_branches (skill_name, branch_name, code, latency_ms, max_rss_kb, complexity_score, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test_skill", "test_branch_opt", "def test_skill(): return 42", 5.2, 100, 30, "merged")
        )
        self.cursor.execute(
            "INSERT INTO skill_branches (skill_name, branch_name, code, latency_ms, max_rss_kb, complexity_score, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test_skill", "test_branch_fail", "def test_skill(): raise Exception", 20.1, 500, 35, "rejected")
        )
        
        # Insert mock sandbox test runs
        self.cursor.execute(
            "INSERT INTO reality_tests (script_name, stderr, exit_code, status) VALUES (?, ?, ?, ?)",
            ("test_skill_verify.py", "", 0, "PASS")
        )
        self.cursor.execute(
            "INSERT INTO reality_tests (script_name, stderr, exit_code, status) VALUES (?, ?, ?, ?)",
            ("test_skill_verify_err.py", "Traceback: ZeroDivisionError", 1, "FAIL")
        )
        
        # Insert mock API limit telemetry
        self.cursor.execute(
            "INSERT INTO limit_telemetry (rpd, rpm, tpm, error_code, latency_ms, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (10, 2, 500, "", 1200, "Mock API Call")
        )
        
        self.conn.commit()
        self.observer = EvolutionObserver(db_path=self.db_path)

    def tearDown(self):
        self.conn.close()

    def test_gather_telemetry_data(self):
        """Verifies that the telemetry gathering helper maps SQLite tables correctly."""
        data = self.observer.gather_telemetry_data()
        
        self.assertIn("skills", data)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(data["skills"][0]["name"], "test_skill")
        self.assertEqual(data["skills"][0]["version"], 2)
        
        self.assertIn("mutation_summary", data)
        self.assertEqual(len(data["mutation_summary"]), 2) # merged and rejected status types
        
        self.assertIn("sandbox_tests", data)
        self.assertEqual(len(data["sandbox_tests"]), 2) # PASS and FAIL tests
        
        self.assertIn("recent_failures", data)
        self.assertEqual(len(data["recent_failures"]), 1)
        self.assertEqual(data["recent_failures"][0]["script"], "test_skill_verify_err.py")
        self.assertEqual(data["recent_failures"][0]["stderr"], "Traceback: ZeroDivisionError")
        
        self.assertIn("api_usage", data)
        self.assertEqual(data["api_usage"]["total_calls"], 1)
        self.assertEqual(data["api_usage"]["total_tokens"], 500)

if __name__ == "__main__":
    unittest.main()
