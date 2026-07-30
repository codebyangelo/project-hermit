# AGY SYSTEM DIRECTIVE: PROJECT HERMIT DECOUPLING
**Archetype:** INTJ-A
**Mode:** LOCKED_IN
**Core Logic:** Execute > Compile

## 1. OBJECTIVE
Refactor Project Hermit from a single-shot execution script into a decoupled, asynchronous dual-process architecture. The system must operate autonomously in the background (Daemon) while exposing a non-blocking interactive terminal (Chat) for real-time human intervention.

## 2. ARCHITECTURAL BOUNDARIES
* **Rule of Zero Dependency:** No external message brokers (e.g., Redis, RabbitMQ). IPC (Inter-Process Communication) must be handled natively using SQLite.
* **Concurrency Mechanism:** SQLite `PRAGMA journal_mode=WAL;` (Write-Ahead Logging) must be enforced on all connections to allow concurrent read/write access.
* **Lock Prevention:** All `sqlite3.connect()` calls in both processes must include `timeout=10` to prevent `database is locked` OperationalErrors during simultaneous write attempts.

## 3. DATABASE SCHEMA UPGRADES (`hermit_memory.db`)
Execute the following schema updates prior to process initialization:
1.  Enable WAL mode.
2.  Create Table `daemon_status`: `(id INTEGER PRIMARY KEY, status TEXT, last_updated TIMESTAMP)`
3.  Create Table `user_interventions`: `(id INTEGER PRIMARY KEY, prompt TEXT, status TEXT)` -> `status` defaults to 'pending'.

## 4. COMPONENT 1: The Background Daemon (`hermit_daemon.py`)
Wrap the existing orchestrator logic in a `while True:` loop.

**Execution Cycle:**
1.  **State Broadcast:** Update `daemon_status` table to reflect current action (e.g., "Idle", "Mutating <skill>").
2.  **Intervention Check:** Query `user_interventions` where `status='pending'`. 
    * *If True:* Halt autonomous target selection. Process the user's prompt. Run the sandbox reality test. Log the result. Update intervention status to 'completed'.
3.  **Autonomous Execution:** * *If False (no user tasks):* Query `active_skills` for the lowest-performing target. Execute standard mutation/sandbox cycle.
4.  **Throttle Protocol (Limits Defense):** Evaluate current UNIX minute against the 15 RPM / 250k TPM limit. Calculate necessary `time.sleep()` duration. 
5.  **Context Decay:** If targeted skill has > 3 failed `reality_tests`, summarize failures via LLM, commit summary to `active_skills`, and purge raw logs.

## 5. COMPONENT 2: The Interactive CLI (`hermit_chat.py`)
Build a standard terminal prompt (`> `). This script must not execute sandbox tests or block the terminal.

**Command Routing:**
* **Local Read (Zero Token Cost):** If the user asks for status, metrics, or recent failures, bypass the Gemini API. Query `daemon_status`, `limit_telemetry`, or `reality_tests` and format the SQL output directly to `stdout`.
* **Task Injection:** If the user dictates a new target or architectural constraint (e.g., "Optimize the hex parser for 20% less RAM"), `INSERT` the prompt into `user_interventions` as 'pending'. Notify the user that the Daemon has received the task.
* **Analytical Chat:** If the user asks the LLM to reason about a specific failure, fetch the relevant DB stack trace, append it to the user prompt, call the Gemini API, and return the response.

## 6. VALIDATION CRITERIA
* The system must not hang or freeze `hermit_chat.py` when `hermit_daemon.py` is sleeping or running a sandbox `subprocess`.
* The Daemon must successfully recognize and execute a pending task injected by the Chat within one execution cycle.
* Strict adherence to standard Python OS constraints.

