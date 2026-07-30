# USAGE.md
## Phase 7 - Usage & Developer Operations Guide

This document provides a comprehensive guide for operating, configuring, monitoring, and interacting with **Project Hermit** (`v0.1.9`).

---

### 1. Quick Start Guide

To launch Project Hermit in autonomous self-optimization mode:

1. **Set your API Key**:
   ```bash
   export GEMINI_API_KEY="your-actual-api-key"
   ```

2. **Start the Autonomous Background Daemon**:
   ```bash
   cd v0.1.9
   python3 hermit_daemon.py
   ```
   *The daemon will continuously run in the background, alternating between Phase 1 (untouched skills) and Phase 2 (bottleneck sort), executing AST math mutations, QUBO bitwise optimizations, and LLM code synthesis inside isolated RAM disks.*

3. **Monitor System Evolution**:
   In a separate terminal, monitor real-time daemon metrics, active skills, and version history:
   ```bash
   python3 monitor_evolution.py
   ```

4. **Launch Interactive Chat CLI**:
   Interact directly with the Hermit system to inspect memory or inject tasks:
   ```bash
   python3 hermit_chat.py
   ```

---

### 2. Common Operations & Commands

#### Running Verification & Unit Tests
* **Verify System Architecture**:
  ```bash
  python3 orchestrator.py --mode shadow_test
  ```
* **Run Integration Test Suite**:
  ```bash
  python3 test_hermit.py
  ```
* **Run Mutator Test Suites**:
  ```bash
  python3 test_math_mutator.py
  python3 test_math_integration.py
  python3 test_qubo_mutator.py
  python3 test_qubo_integration.py
  ```

#### Monitoring System Health & Memory
* **Query SQLite Database Table Counts**:
  ```bash
  python3 -c "import sqlite3; conn = sqlite3.connect('hermit_memory.db'); print([r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\'table\';').fetchall()])"
  ```
* **Inspect Version History**:
  ```bash
  python3 -c "import sqlite3; conn = sqlite3.connect('hermit_memory.db'); print(conn.execute('SELECT skill_name, version, strategy, latency_ms FROM version_history ORDER BY id DESC LIMIT 10').fetchall())"
  ```

---

### 3. CLI Options & Runtime Configurations

* **`hermit_daemon.py`**:
  * Runs the dual-phase scheduler loop.
  * Auto-stops when the linear regression plateau threshold is reached (latency slope improvement < 5% over 20 minutes) or budget caps (5M tokens, 2 hours) are exceeded.
* **`orchestrator.py`**:
  * Handles host controller actions, skill registration, harness verification, and Pareto scoring.
  * Can be invoked in `--mode shadow_test` for system verification without launching the full daemon.
