# Project Hermit v0.0.8 - Hardened Auditable Logging & Multi-Skill Optimization Balancing (Finalized)

> [!NOTE]
> This version is finalized and stable. Development has moved to [v0.0.9](file:///root/home/projects/project-hermit/v0.0.9) to focus on operational resilience and framework exclusions.

Version `v0.0.8` implements a detailed thoughts ledger to trace agent decisions and optimizations, dynamically resolves skill targets inside the interactive CLI chat, and introduces balanced multi-skill optimization scheduling.

## Core Features

1. **Hardened Auditable Thoughts Ledger (`thoughts.txt`):**
   * Automatically traces all outbound LLM prompts and raw JSON responses.
   * Records specific optimization rationales, adversarial QA test cases, sandbox telemetry runs (exit codes, latency, max RSS), and merge decisions for transparency and historical learning.

2. **Dynamic Target Skill Resolution:**
   * CLI chat (`hermit_chat.py`) dynamically scans the user prompt for registered active skill names.
   * If a registered skill name (e.g. `get_state_hash`) is mentioned, it targets it automatically.
   * If no skill name is found, it automatically defaults to the most recently registered active skill in the database instead of hardcoding target names.

3. **Multi-Skill Round-Robin & Plateau Discovery:**
   * The background daemon (`hermit_daemon.py`) sorts registered active skills by version number to prioritize lower-version skills, creating a natural round-robin optimization cadence.
   * If an optimization step plateaus (fails to find any Pareto improvements), the daemon immediately runs a discovery scan to detect and register other bottlenecks.

4. **On-Demand Codebase Scanning CLI Command:**
   * Added the `discover` command to `hermit_chat.py` to queue a codebase scan task immediately, letting the daemon locate new optimization targets on-demand.

## Setup & Testing

1. Initialize a clean database:
   ```bash
   rm -f hermit_memory.db hermit_memory.db-wal hermit_memory.db-shm thoughts.txt execution.log && python3 init_db.py
   ```
2. Start the background daemon to discover and evolve skills:
   ```bash
   export GEMINI_API_KEY=<your_key>
   python3 hermit_daemon.py
   ```
3. In a separate terminal, launch the interactive CLI chat:
   ```bash
   python3 hermit_chat.py
   ```
4. Monitor progress and compile reports:
   ```bash
   python3 monitor_evolution.py
   ```
5. Trace thoughts and API traffic:
   ```bash
   cat thoughts.txt
   ```
