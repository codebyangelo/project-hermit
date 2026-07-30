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
        CREATE TABLE IF NOT EXISTS adversarial_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            skill_name TEXT,
            test_code TEXT
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

    def test_discover_and_register_new_skill(self):
        """Verifies autonomous skill discovery and database registration."""
        # Mock call_gemini_api
        original_call = self.orchestrator.call_gemini_api
        mock_response = {
            "success": True,
            "text": json.dumps({
                "selected_file": "project-lobster/src/iron_dome.py",
                "skill_name": "scan_allowlist",
                "description": "Mocked scanner allowlist logic",
                "baseline_code": "def scan_allowlist(code): return None",
                "verification_harness": "assert scan_allowlist('a') is None\nprint('Verification Successful')"
            }),
            "tokens": 100,
            "latency_ms": 50
        }
        self.orchestrator.call_gemini_api = lambda prompt, system_instruction=None: mock_response
        
        try:
            success, skill_name = self.orchestrator.discover_and_register_new_skill()
            self.assertTrue(success)
            self.assertEqual(skill_name, "scan_allowlist")
            
            # Check skill in DB
            skill = self.orchestrator.get_skill("scan_allowlist")
            self.assertIsNotNone(skill)
            desc, code, version = skill
            self.assertIn("Mocked scanner allowlist logic", desc)
            self.assertIn("=== HARNESS ===", desc)
            self.assertIn("assert scan_allowlist", desc)
            self.assertEqual(code, "def scan_allowlist(code): return None")
            self.assertEqual(version, 1)
        finally:
            self.orchestrator.call_gemini_api = original_call

    def test_self_patching(self):
        """Verifies introspective self-patching and regression check behavior."""
        import sys
        
        # 1. Create a dummy python file in the test dir containing a function
        dummy_file_content = (
            "def my_test_helper(x):\n"
            "    return x + 1\n"
        )
        dummy_file_path = os.path.join(self.test_dir, "dummy_helper.py")
        with open(dummy_file_path, "w") as f:
            f.write(dummy_file_content)
            
        # 2. Mock os.path.dirname(os.path.abspath(__file__)) inside patch_source_file_with_skill
        # to point to self.test_dir so it scans our dummy file instead of the actual project dir
        import unittest.mock as mock
        with mock.patch("os.path.dirname") as mock_dirname:
            # When dirname is called on orchestrator.py, return the test directory
            mock_dirname.return_value = self.test_dir
            
            # Mock subprocess.run to simulate unit tests passing
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "Unit tests passed."
                
                optimized_code = (
                    "def my_test_helper(x):\n"
                    "    # optimized version\n"
                    "    return x * 1\n"
                )
                
                success = self.orchestrator.patch_source_file_with_skill("my_test_helper", optimized_code)
                self.assertTrue(success)
                
                # Check target file content was updated
                with open(dummy_file_path, "r") as f:
                    updated_content = f.read()
                self.assertIn("# optimized version", updated_content)
                self.assertNotIn("return x + 1", updated_content)
                
                # Verify backup file was deleted
                self.assertFalse(os.path.exists(dummy_file_path + ".bak"))

            # Test rollback: Mock subprocess.run to simulate unit tests failing
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "Compilation error."
                mock_run.return_value.stdout = "Unit tests failed."
                
                broken_code = (
                    "def my_test_helper(x):\n"
                    "    raise ValueError('broken')\n"
                )
                
                success = self.orchestrator.patch_source_file_with_skill("my_test_helper", broken_code)
                self.assertFalse(success)
                
                # Check target file content was rolled back to the previous optimized state
                with open(dummy_file_path, "r") as f:
                    rolled_back_content = f.read()
                self.assertIn("# optimized version", rolled_back_content)
                self.assertNotIn("raise ValueError", rolled_back_content)
                self.assertFalse(os.path.exists(dummy_file_path + ".bak"))

    def test_call_gemini_api_retry_behavior(self):
        """Verifies that call_gemini_api retries on transient exceptions and returns success if one succeeds."""
        import unittest.mock as mock
        
        # Mock genai.Client
        with mock.patch("google.genai.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client
            
            # Setup a side effect where it raises Exception twice, then succeeds on the third attempt
            mock_interaction = mock.MagicMock()
            mock_step = mock.MagicMock()
            mock_step.type = "model_output"
            mock_content = mock.MagicMock()
            mock_content.text = "Success Response"
            mock_step.content = [mock_content]
            mock_interaction.steps = [mock_step]
            
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Temporary connection error")
                return mock_interaction
            
            mock_client.interactions.create.side_effect = side_effect
            
            # Temporarily configure API key to bypass has_api_access check
            original_key = self.orchestrator.api_key
            self.orchestrator.api_key = "dummy_key"
            
            try:
                # Set a small sleep pacing mock to avoid test latency
                with mock.patch("time.sleep") as mock_sleep:
                    res = self.orchestrator.call_gemini_api("Hello", "Test System Instruction")
                    
                    self.assertTrue(res["success"])
                    self.assertEqual(res["text"], "Success Response")
                    self.assertEqual(call_count, 3)
                    self.assertEqual(mock_sleep.call_count, 2) # slept 2 times for backoff retries
            finally:
                self.orchestrator.api_key = original_key

    def test_correlation_telemetry_queries(self):
        """Verifies that orchestrator can retrieve historical variants and recent failure logs."""
        skill_name = "test_correlation_skill"
        
        # 1. Verify get_skill_history returns empty when no branches exist
        history = self.orchestrator.get_skill_history(skill_name)
        self.assertEqual(history, [])
        
        # Save a branch variant
        self.orchestrator.save_branch_variant(skill_name, "test_branch", "def test_correlation_skill(): pass", 10.0, 100, 10, "candidate")
        
        # Retrieve history and verify details
        history = self.orchestrator.get_skill_history(skill_name)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["branch_name"], "test_branch")
        self.assertEqual(history[0]["status"], "candidate")
        
        # 2. Verify get_recent_failures returns empty when no failures exist
        failures = self.orchestrator.get_recent_failures(skill_name)
        self.assertEqual(failures, [])
        
        # Log a failed sandbox run to DB
        from sandbox import SandboxResult
        res = SandboxResult(
            script_name="test_correlation_skill_verify.py",
            script_content="raise Exception()",
            input_data="",
            stdout="",
            stderr="Traceback: NameError",
            exit_code=1,
            duration_ms=5.0,
            max_rss_kb=10
        )
        res.log_to_db(self.db_path)
        
        # Retrieve failures and verify details
        failures = self.orchestrator.get_recent_failures(skill_name)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["script_name"], "test_correlation_skill_verify.py")
        self.assertEqual(failures[0]["stderr"], "Traceback: NameError")

if __name__ == "__main__":
    unittest.main()
