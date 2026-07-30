# PROJECT_OVERVIEW.md
## Phase 1 - Universal Project Purpose & Architectural Core

This document outlines the core purpose, problem statement, engineering goals, target users, scope, non-goals, and design philosophy of **Project Hermit**, synthesized from empirical project evidence.

---

### 1. Project Purpose

**Project Hermit** is an autonomous, self-evolving multi-agent system and dynamic tool platform designed to perform closed-loop self-optimization and code mutation on software skill payloads. It operates as an offline-first, self-contained optimization daemon (`hermit_daemon.py`) that continuously discovers, profiles, refactors, and tests python skill payload functions in isolated sandbox environments (`sandbox.py`) using LLM-driven synthesis combined with deterministic mathematical and AST mutators (`math_mutator.py`, `qubo_mutator.py`).

---

### 2. Problem Statement

Traditional AI code generation frameworks suffer from several systemic operational failures when running long-horizon autonomous self-improvement tasks:

1. **Queue Starvation & Priority Inversion**: Pure bottleneck scheduling (`AVG(duration_ms) DESC`) causes high-latency functions to monopolize mutation cycles, leaving complex untouched skills unoptimized.
2. **Strategy Oscillation & Rebound Loops**: Pure count-based strategy banning penalizes successful mutations, causing optimization loops that continuously cycle between previously discarded code variants.
3. **Measurement Distortion & Drift**: Inconsistent sandbox memory measurements (e.g. cumulative `RUSAGE_CHILDREN` reporting 0.0 KB RAM deltas) and harness drift lead to invalid latency baseline comparisons.
4. **Thermal Throttling & Resource Fatigue**: Long-running background daemons ignore hardware thermal constraints and API quota caps, leading to rate limit (429) loops and thermal degradation.
5. **Self-Mutation Instability**: Unrestricted self-modification risks mutating critical orchestrator logic (scheduler, sandbox isolation, verification engine), destroying system integrity.

---

### 3. Engineering Goals

Project Hermit addresses these failures through five foundational engineering pillars:

* **Closed-Loop Self-Evolution**: Safely mutate and optimize python function payloads (`dynamic_mcp_server.py`) without modifying the host orchestration engine.
* **Dual-Phase Scheduling**: Balance exploration (Phase 1: untouched headroom targeting) and exploitation (Phase 2: bottleneck sort with concurrency limits).
* **Deterministic Verification & Safety**: Enforce AST-level code safety checks, pre-execution static analysis, dynamic `RLIMIT_AS` memory bounds, and fork-based grandchild RAM measurement in `sandbox.py`.
* **Immutable Core Security**: Strictly protect host looper functions (`get_next_target`, `sandbox_run`, `detect_oscillation`) from self-mutation via an immutable function registry.
* **Quota & Thermal-Aware Resilience**: Dynamically rotate multi-key API pools (`api_keys.txt`) based on RPM/TPM headroom and scale sandbox parallelism based on CPU thermal trends.

---

### 4. Target Users

* **Autonomous AI System Researchers**: Engineers researching self-improving code synthesis and multi-agent coordination.
* **High-Performance Systems & Algorithm Engineers**: Developers seeking automated AST constant-folding, algebraic simplification, and QUBO/quantum-classical algorithm optimization.
* **Edge & Offline Infrastructure Developers**: Users deploying lightweight agentic daemons in resource-constrained environments (e.g., Linux, ARM/mobile host containers).

---

### 5. Scope & Non-Goals

#### In-Scope:
* Autonomous discovery and registration of Python skill payload functions into `hermit_memory.db`.
* Multi-objective Pareto score evaluation (Latency gate, Memory guard, Code complexity tiebreaker).
* AST mathematical mutations, quantum-classical QUBO bitwise optimizations, and LLM code synthesis.
* Cross-skill regression testing using static dependency graphs (`skill_dependencies`).
* Automated 30-minute database backups (`VACUUM INTO`) and integrity verification (`PRAGMA integrity_check`).

#### Non-Goals:
* Unrestricted, arbitrary self-modification of the core host controller (`orchestrator.py`) or sandbox kernel (`sandbox.py`).
* Web UI / Graphical user interface design (Project Hermit is exclusively CLI/Daemon based).
* Blind code modification without empirical sandbox validation and regression verification.

---

### 6. Design Philosophy & Architectural Principles

1. **Evidence-Based Acceptance**: No code mutation is merged into `version_history` unless validated by a 100% passing test harness hash and measurable improvement score.
2. **Decoupled Payload & Host Architecture**: Host engine logic (`orchestrator.py`) is decoupled from mutable payloads (`dynamic_mcp_server.py`), allowing hot-reloading (`importlib.reload`) without process termination.
3. **Fail-Safe Self-Healing & Rollback**: Automatic fallback to versioned database snapshots (`.db`) and file backups upon test failure or scheduled validation anomalies.
