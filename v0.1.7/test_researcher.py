import os
import unittest
import tempfile
import sqlite3
from unittest.mock import MagicMock
from researcher import EvolutionResearcher

class TestEvolutionResearcher(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and test database
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_hermit_researcher.db")
        
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
        CREATE TABLE IF NOT EXISTS skill_research_notes (
            skill_name TEXT PRIMARY KEY,
            notes TEXT NOT NULL,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.test_dir)

    def test_researcher_notes_storage(self):
        """Verifies that the researcher can store and retrieve notes correctly."""
        researcher = EvolutionResearcher(db_path=self.db_path)
        
        # Verify note is initially empty
        note = researcher.get_research_note("test_skill")
        self.assertIsNone(note)
        
        # Store note
        researcher.store_research_note("test_skill", "Use bytes instead of memoryview for sliding search.")
        
        # Retrieve and verify
        note = researcher.get_research_note("test_skill")
        self.assertEqual(note, "Use bytes instead of memoryview for sliding search.")

    def test_researcher_fetching_failures(self):
        """Verifies that the researcher correctly queries recent sandbox failures."""
        researcher = EvolutionResearcher(db_path=self.db_path)
        
        # Log a failed run to reality_tests
        self.cursor.execute("""
            INSERT INTO reality_tests (script_name, script_content, stderr, stdout, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "test_skill_verify.py",
            "def test_skill(): pass",
            "Traceback: AttributeError on memoryview",
            "Failure logs output",
            "FAIL"
        ))
        self.conn.commit()
        
        # Query failures
        failures = researcher.get_recent_failures("test_skill")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["script_name"], "test_skill_verify.py")
        self.assertEqual(failures[0]["stderr"], "Traceback: AttributeError on memoryview")

    def test_research_failures_api_call(self):
        """Verifies call_gemini_api interaction and database note persistence."""
        # Log a failed run
        self.cursor.execute("""
            INSERT INTO reality_tests (script_name, script_content, stderr, stdout, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "test_skill_verify.py",
            "def test_skill(): pass",
            "Traceback: AttributeError",
            "",
            "FAIL"
        ))
        self.conn.commit()
        
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.call_gemini_api.return_value = {
            "success": True,
            "text": "DIAGNOSIS: memoryview find error.\nSTRATEGY: Cast memoryview to bytes.",
            "error": None
        }
        
        researcher = EvolutionResearcher(db_path=self.db_path, orchestrator=mock_orchestrator)
        
        # Run research
        notes = researcher.research_failures("test_skill", "def test_skill(): pass", "Sample Description")
        
        # Verify notes returned
        self.assertIn("STRATEGY: Cast memoryview to bytes.", notes)
        
        # Verify notes stored in database
        stored_note = researcher.get_research_note("test_skill")
        self.assertEqual(stored_note, notes)
        mock_orchestrator.call_gemini_api.assert_called_once()

if __name__ == "__main__":
    unittest.main()
