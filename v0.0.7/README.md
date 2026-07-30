# Project Hermit v0.0.7 - Dynamic & Autonomous Skill Discovery

Version `v0.0.7` implements dynamic codebase scanning, enabling Project Hermit to autonomously discover computational bottleneck functions from the active workspace folders instead of relying on hardcoded targets.

## Core Features
1. **AST Codebase Scanning Heuristics (`orchestrator.py`):**
   * Dynamically crawls the prioritized active directories (e.g. `project-lobster/src` and `project-mantis/agent_v0.5.5`).
   * Uses an `ast` parse tree to isolate function definitions that contain computational constructs (such as loops, comprehensions, or string/byte seek methods) and targets functions of length between 5 and 80 lines.

2. **Self-Contained Code Extraction:**
   * Prompts the Gemini Discovery Agent to pick a single candidate function from the list, extract its baseline code, and design a high-pressure verification harness.
   * Requires that any standard library imports needed by the function (e.g. `import hashlib`, `import json`) are prepended directly to the top of the function definition to maintain isolation.

3. **Compatible Harness Database Contracts:**
   * The verification harness is embedded inside the skill's description column in the database (delimited by `=== HARNESS ===`), maintaining compatibility without SQLite schema migrations.

4. **Dynamic Monitoring:**
   * `monitor_evolution.py` dynamically loads the discovered skill details, evaluates its branch variants, and compiles the final markdown report.

## Setup & Testing
1. Initialize a clean database:
   ```bash
   rm -f hermit_memory.db && python3 init_db.py
   ```
2. Start the background daemon to discover and evolve a skill:
   ```bash
   export GEMINI_API_KEY=<your_key>
   python3 hermit_daemon.py
   ```
3. Monitor progress and compile reports:
   ```bash
   python3 monitor_evolution.py
   ```
