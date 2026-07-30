# Project Hermit v0.0.9 - Resilient Operations & Hardened Infrastructure Exclusions

Version `v0.0.9` inherits the database and the 76 registered skills from `v0.0.8`. It introduces robust connection failure resilience and strict framework infrastructure exclusions to ensure stability and efficiency during autonomous optimizations.

## Core Features

1. **Hardened Infrastructure Exclusions (`EXCLUDED_SKILLS`):**
   * Configured a strict blacklist in [orchestrator.py](file:///root/home/projects/project-hermit/v0.0.9/orchestrator.py) containing **22 Framework Infrastructure and CLI utility skills** (e.g. `list_skills`, `show_failures`, `__init__`, `compile_report`).
   * Prevents the Discovery Agent from scanning or registering these CLI/orchestrator helper functions.
   * Excludes them from the evolution loop to focus all processing power and API tokens on high-impact, CPU-bound DFIR sieve and carving code (e.g. `carve_memory_strings`, `search_disk_timeline`, `score_pid_table`).

2. **Network Connection Resilience:**
   * Integrated a 5-attempt exponential backoff retry mechanism inside `call_gemini_api` to handle network disconnects or API server timeouts.
   * Successfully tested to survive and recover from internet drops without loop crashes.

3. **Skills Categorization Document (`skills_analysis_report.md`):**
   * Includes a copy of [skills_analysis_report.md](file:///root/home/projects/project-hermit/v0.0.9/skills_analysis_report.md) in the project root.
   * Catalogs and groups the 76 active skills from `hermit_memory.db` into logical domains (Carving, Sieve, Utilities, and Infrastructure) to guide future optimization decisions.

4. **Multi-Skill Scheduling & Plateau scans (Inherited):**
   * Daemon loops through active skills ordered by version (lowest optimized first) and triggers discovery scans when optimizations plateau.

## Setup & Testing

1. Initialize a clean database (if rebuilding from scratch):
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
4. Run integration tests (resilient to slow/stuck network loops):
   ```bash
   python3 test_integration.py
   ```
5. Monitor progress and compile reports:
   ```bash
   python3 monitor_evolution.py
   ```
