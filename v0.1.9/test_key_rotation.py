import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from orchestrator import Orchestrator

class TestKeyRotation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_hermit_keys.db")
        
        # Write a mock api_keys.txt in the test directory
        self.keys_file = os.path.join(self.test_dir, "api_keys.txt")
        with open(self.keys_file, "w") as f:
            f.write("# Mock Keys\nMOCK_KEY_1\nMOCK_KEY_2\nMOCK_KEY_3\n")
            
        # Initialize SQLite for rolling telemetry logs
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
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
        conn.commit()
        conn.close()

        # Deterministic key selection mock
        self.choices_patcher = patch("random.choices", side_effect=lambda population, weights=None, k=1: [population[0]])
        self.mock_choices = self.choices_patcher.start()

    def tearDown(self):
        self.choices_patcher.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_key_loading(self):
        """Verifies that Orchestrator loads keys from api_keys.txt."""
        # Temporarily change current working directory to test_dir to read api_keys.txt
        old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            ord_inst = Orchestrator(db_path=self.db_path)
            self.assertEqual(len(ord_inst.api_keys), 3)
            self.assertEqual(ord_inst.api_key, "MOCK_KEY_1")
        finally:
            os.chdir(old_cwd)

    @patch("google.genai.Client")
    def test_quota_exception_rotates_keys(self, mock_client_class):
        """Verifies that a 429 quota exception triggers API key rotation and retry."""
        # 1. Setup client mock to fail on key 1 with 429, then succeed on key 2
        mock_client_instance_1 = MagicMock()
        mock_client_instance_2 = MagicMock()
        
        # First call (on MOCK_KEY_1) raises 429 Quota Exceeded Exception
        mock_client_instance_1.interactions.create.side_effect = Exception("ResourceExhausted: 429 Quota Exceeded")
        
        # Second call (on MOCK_KEY_2) succeeds
        mock_step = MagicMock()
        mock_step.type = "model_output"
        mock_content = MagicMock()
        mock_content.text = "Success Response"
        mock_step.content = [mock_content]
        
        mock_interaction = MagicMock()
        mock_interaction.steps = [mock_step]
        mock_client_instance_2.interactions.create.return_value = mock_interaction
        
        # Setup Client constructor to return instance 1 first, then instance 2
        mock_client_class.side_effect = [mock_client_instance_1, mock_client_instance_2]

        old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            ord_inst = Orchestrator(db_path=self.db_path)
            self.assertEqual(ord_inst.api_key, "MOCK_KEY_1")
            
            # Disable pacing wait during test
            with patch("time.sleep") as mock_sleep:
                res = ord_inst.call_gemini_api("Hello prompt", "System instruction")
                
                self.assertTrue(res["success"])
                self.assertEqual(res["text"], "Success Response")
                # Assert index rotated to 1 (MOCK_KEY_2)
                self.assertEqual(ord_inst.active_key_index, 1)
                self.assertEqual(ord_inst.api_key, "MOCK_KEY_2")
                
                # Check Client called with correct keys sequentially
                mock_client_class.assert_any_call(api_key="MOCK_KEY_1")
                mock_client_class.assert_any_call(api_key="MOCK_KEY_2")
        finally:
            os.chdir(old_cwd)

if __name__ == "__main__":
    unittest.main()
