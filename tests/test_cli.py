import unittest
import os
import tempfile
import shutil
import io
import contextlib
from hermit.cli import build_parser, cmd_status, cmd_init_db
from hermit import __version__


class TestHermitCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_cli_hermit.db")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cli_version(self):
        parser = build_parser()
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                parser.parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_init_db_and_status(self):
        parser = build_parser()
        
        # Test init-db
        args_init = parser.parse_args(["init-db", "--db", self.db_path])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cmd_init_db(args_init)
        self.assertEqual(exit_code, 0)
        self.assertTrue(os.path.exists(self.db_path))

        # Test status
        args_status = parser.parse_args(["status", "--db", self.db_path])
        stdout_status = io.StringIO()
        with contextlib.redirect_stdout(stdout_status):
            exit_code = cmd_status(args_status)
        self.assertEqual(exit_code, 0)
        output = stdout_status.getvalue()
        self.assertIn("Project Hermit", output)
        self.assertIn("Active Skills", output)


if __name__ == "__main__":
    unittest.main()
