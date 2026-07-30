# Project Hermit v0.0.2 - Background Daemon & Interactive CLI

Version `v0.0.2` transitions Project Hermit from a manually triggered script into a continuously running daemon with an interactive command-line interface.

## Core Features
1. **Background Daemon (`hermit_daemon.py`):**
   * Continuously polls SQLite database tables (in WAL mode for concurrency) to check for pending user interventions or run autonomous optimization routines.
   * Periodically broadcasts heartbeat logs and execution states into the `daemon_status` table.

2. **Interactive CLI Chat (`hermit_chat.py`):**
   * Multi-threaded terminal client that allows the user to monitor daemon status, query currently registered skills, and queue new optimization interventions.

3. **Concurrency & Integration Check (`test_integration.py`):**
   * End-to-end integration test verifying that a task submitted to the database is parsed, compiled, executed, and completed by the background daemon thread.
