import unittest
import os
import sqlite3
import tempfile
import shutil

from orchestrator import Orchestrator

class TestQUBOIntegration(unittest.TestCase):
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

    def test_qubo_evolution_tandem(self):
        """Verifies that classical QUBO solver optimizations (like local delta updates) are proposed and merged."""
        skill_name = "solve_qubo_sa"
        description = "Runs simulated annealing to solve a QUBO."
        # A slow baseline QUBO solver that computes full energy every step (O(N^2))
        code = (
            "def solve_qubo_sa(Q, n):\n"
            "    state = [0] * n\n"
            "    # Baseline computes full matrix product on every flip\n"
            "    energy = sum(Q[i][j] * state[i] * state[j] for i in range(n) for j in range(n))\n"
            "    return state, energy\n"
        )
        
        self.orchestrator.register_or_update_skill(skill_name, description, code)
        
        harness = (
            "Q = [[1, -2], [-2, 1]]\n"
            "state, energy = solve_qubo_sa(Q, 2)\n"
            "assert len(state) == 2\n"
            "print('Pass')\n"
        )
        
        # Mock Gemini API response to suggest a local delta update variant for the QUBO solver
        self.orchestrator.api_key = "dummy_key"
        self.orchestrator.call_gemini_api = lambda prompt, sys_inst=None: {
            "success": True,
            "text": (
                '{\n'
                '  "variants": [\n'
                '    {\n'
                '      "branch_name": "qubo_local_delta",\n'
                '      "rationale": "Optimized simulated annealing to calculate incremental energy difference instead of O(N^2) product.",\n'
                '      "code": "def solve_qubo_sa(Q, n):\\n    state = [0] * n\\n    # Fast O(N) delta update\\n    energy = 0\\n    return state, energy\\n"\n'
                '    }\n'
                '  ],\n'
                '  "adversarial_test_code": "state, energy = solve_qubo_sa([[0]], 1); assert energy == 0"\n'
                '}'
            ),
            "tokens": 10,
            "latency_ms": 1
        }
        
        success, msg = self.orchestrator.run_evolution_step(skill_name, harness)
        self.assertTrue(success)
        self.assertIn("INTEGRATION SUCCESS", msg)
        
        # Verify the evolved skill is saved as version 2
        skill = self.orchestrator.get_skill(skill_name)
        self.assertIsNotNone(skill)
        desc, evolved_code, version = skill
        
        self.assertEqual(version, 2)
        self.assertIn("Fast O(N) delta update", evolved_code)
        print("QUBO Integration test passed.")

if __name__ == "__main__":
    unittest.main()
