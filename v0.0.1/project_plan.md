# SYSTEM CONTEXT: PROJECT HERMIT

## 1. PROJECT OVERVIEW
**Codename:** Project Hermit
**Classification:** Autonomous Metacognitive Agent / LLM-Guided Evolutionary Search Engine.
**Objective:** To establish a self-evolving loop where an agent reasons about its own LLM integration, maps its API constraints, and autonomously tests, validates, and integrates new architectural approaches to bypass human legacy bias and optimize hardware/resource efficiency.

## 2. CORE ARCHITECTURE
The system operates as an automated CI/CD pipeline governed by an LLM, restricted entirely to native OS binaries and Zero Dependency engineering. 

* **The Orchestrator:** The static Python core that initializes the Gemini 3.1 Flash-Lite API, reads state, and triggers the Evolution Cycle.
* **The Sandbox:** An isolated subprocess execution environment where the agent safely simulates and reality-tests its own generated code mutations before committing them to the main architecture.
* **The Memory & RAG Engine (SQLite3):** A native, lightweight database mapping three critical states:
    * `limit_telemetry`: Tracks hard/soft API ceilings (RPD, RPM, TPM, error codes, latency).
    * `reality_tests`: Logs every script simulation, input, `stdout`/`stderr`, and binary pass/fail state.
    * `active_skills`: A registry of integrated, validated functions.
* **The Verification Baseline:** Test-Driven Development via native `unittest`. Architectural mutations must pass reality tests against hard metrics (speed, token efficiency, memory overhead) before integration.

## 3. OPERATIONAL DIRECTIVES & CONSTRAINTS
* **Zero Dependency:** Reject third-party abstractions. Rely on standard Python libraries (`sqlite3`, `subprocess`, `unittest`) and native OS binaries. 
* **Hardware Optimization (Machine-to-Machine):** Strip away human-readable formatting. Default to raw data transformation (e.g., JSON arrays) to process heavy workloads (like DFIR memory analysis) within constrained environments (e.g., Termux, < 1.5GB RAM availability).
* **Metrics > Feelings:** Code mutations are evaluated strictly mathematically. If a mutation uses less RAM or fewer tokens than the baseline, it is integrated. If it bloats the system or fails a limit, it is logged in the DB as a failure to prevent regression.
* **Self-Synthesizing Knowledge:** The agent does not ingest external documentation. It farms its own empirical data by pushing limits, forcing failures, logging the stack traces, and learning its actual boundaries.

## 4. IMMEDIATE EXECUTION PATH
1.  Initialize the SQLite database structure (`hermit_memory.db`) with the required tables (`limit_telemetry`, `reality_tests`, `active_skills`).
2.  Draft the baseline Orchestrator script to establish the execution loop and API communication.
3.  Implement the Sandbox environment using `subprocess` with strict timeout controls to ensure runaway AI-generated scripts do not hang the environment.

