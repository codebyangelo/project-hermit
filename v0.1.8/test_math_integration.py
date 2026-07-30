import unittest
import os
import sqlite3
import tempfile
import shutil

from orchestrator import Orchestrator
from sandbox import run_in_sandbox

class TestMathIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_hermit_memory.db")
        
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
        
        self.orchestrator = Orchestrator(db_path=self.db_path)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.test_dir)

    def test_math_evolution_tandem(self):
        """Verifies that mathematical mutations (like x**2 -> x*x) are automatically generated and preferred during evolution."""
        # 1. Register a math-heavy skill with slow x**2 power operations
        skill_name = "sum_of_squares"
        description = "Computes sum of squares."
        code = (
            "def sum_of_squares(n):\n"
            "    total = 0\n"
            "    for i in range(n):\n"
            "        total += i ** 2\n"
            "    return total\n"
        )
        
        self.orchestrator.register_or_update_skill(skill_name, description, code)
        
        # Verification harness that checks correctness
        harness = (
            "import time\n"
            "start = time.perf_counter()\n"
            "res = sum_of_squares(1000)\n"
            "duration = (time.perf_counter() - start) * 1000\n"
            "assert res == 332833500, f'Got: {res}'\n"
            "print('Pass')\n"
        )
        
        # 2. Mock call_gemini_api to return empty variants, forcing it to rely on the math_mutator's AST variants
        # and to return a verified dummy adversarial QA test so the QA step passes
        self.orchestrator.api_key = "dummy_key"
        self.orchestrator.call_gemini_api = lambda prompt, sys_inst=None: {
            "success": True,
            "text": '{"variants": [], "adversarial_test_code": "assert sum_of_squares(5) == 30"}',
            "tokens": 10,
            "latency_ms": 1
        }
        
        # Run evolution step
        success, msg = self.orchestrator.run_evolution_step(skill_name, harness)
        self.assertTrue(success)
        self.assertIn("INTEGRATION SUCCESS", msg)
        
        # 3. Retrieve the evolved skill from DB and check that the math AST mutator succeeded in optimizing the code
        skill = self.orchestrator.get_skill(skill_name)
        self.assertIsNotNone(skill)
        desc, evolved_code, version = skill
        
        self.assertEqual(version, 2)
        # It should have transformed `i ** 2` to `i * i`
        self.assertIn("i * i", evolved_code)
        self.assertNotIn("i ** 2", evolved_code)
        print("Integration test passed: Evolved code:\n", evolved_code)

if __name__ == "__main__":
    unittest.main()
