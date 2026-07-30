import unittest
import os
import sqlite3
import json
import tempfile
import shutil

from sandbox import run_in_sandbox, SandboxResult
from orchestrator import Orchestrator

class TestProjectHermit(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests to avoid touching production data
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_hermit_memory.db")
        
        # Initialize test database tables
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
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
        CREATE TABLE IF NOT EXISTS active_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            skill_name TEXT UNIQUE,
            description TEXT,
            code TEXT,
            version INTEGER DEFAULT 1
        );
        """)
        self.conn.commit()
        
        # Instantiate Orchestrator with the test DB
        self.orchestrator = Orchestrator(db_path=self.db_path)

    def tearDown(self):
        self.conn.close()
        # Clean up temporary test directory
        shutil.rmtree(self.test_dir)

    def test_sandbox_success(self):
        """Verifies sandbox executes valid Python code and logs details successfully."""
        script = "print('Hello Test!')"
        res = run_in_sandbox(script, "test_success.py", cwd=self.test_dir)
        
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Hello Test!", res.stdout)
        self.assertEqual(res.stderr, "")
        self.assertGreaterEqual(res.duration_ms, 0)
        self.assertGreaterEqual(res.max_rss_kb, 0)
        self.assertEqual(res.status, "PASS")

        # Test DB insertion
        test_id = res.log_to_db(self.db_path)
        self.assertIsNotNone(test_id)
        
        # Verify it exists in DB
        self.cursor.execute("SELECT script_name, status FROM reality_tests WHERE id = ?", (test_id,))
        row = self.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "test_success.py")
        self.assertEqual(row[1], "PASS")

    def test_sandbox_timeout(self):
        """Verifies sandbox handles timeout exceptions properly."""
        script = "import time; time.sleep(2)"
        res = run_in_sandbox(script, "test_timeout.py", timeout_sec=0.5, cwd=self.test_dir)
        
        self.assertEqual(res.exit_code, -1)
        self.assertIn("[TIMEOUT]", res.stderr)
        self.assertEqual(res.status, "FAIL")

    def test_orchestrator_skill_registry(self):
        """Verifies skill registration and retrieval logic."""
        skill_name = "test_func"
        description = "A simple test function"
        code = "def test_func(): pass"
        
        # Registration
        success = self.orchestrator.register_or_update_skill(skill_name, description, code)
        self.assertTrue(success)
        
        # Retrieval
        skill = self.orchestrator.get_skill(skill_name)
        self.assertIsNotNone(skill)
        self.assertEqual(skill[0], description)
        self.assertEqual(skill[1], code)
        self.assertEqual(skill[2], 1) # version 1
        
        # Update
        updated_code = "def test_func(): print('updated')"
        self.orchestrator.register_or_update_skill(skill_name, description, updated_code)
        
        skill = self.orchestrator.get_skill(skill_name)
        self.assertEqual(skill[1], updated_code)
        self.assertEqual(skill[2], 2) # version 2

    def test_rolling_telemetry(self):
        """Verifies limit telemetry logging and calculation of rolling values."""
        # Check initial state (should be zeros)
        rpd, rpm, tpm = self.orchestrator.get_rolling_telemetry()
        self.assertEqual(rpd, 0)
        self.assertEqual(rpm, 0)
        self.assertEqual(tpm, 0)

        # Log some API calls
        self.orchestrator.log_api_call(1, 1, 150, None, 100, "Test Call 1")
        self.orchestrator.log_api_call(2, 2, 250, "HTTP 429", 120, "Test Call 2")
        
        # Re-fetch rolling telemetry
        rpd, rpm, tpm = self.orchestrator.get_rolling_telemetry()
        self.assertEqual(rpd, 2)
        self.assertEqual(rpm, 2)
        self.assertEqual(tpm, 400) # 150 + 250

if __name__ == "__main__":
    unittest.main()
