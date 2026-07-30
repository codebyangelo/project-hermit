# FEATURES.md
## Phase 5 - Comprehensive Feature Inventory

This document details the functional features, mathematical mutators, autonomous agents, and scheduling mechanisms implemented in **Project Hermit** (`v0.1.9`).

---

### 1. Engine Core Features

#### Feature 1: Host Controller & Decoupled Dynamic MCP Payload
* **Purpose**: Allows dynamic mutation and optimization of target python skills without modifying or restarting the host orchestrator process.
* **Inputs**: Target skill name, mutated python code candidate string, frozen harness baseline hash (`harness_hash`).
* **Outputs**: Verification test result, updated skill registry entry, hot-reloaded module state (`importlib.reload`).
* **Dependencies**: `orchestrator.py`, `dynamic_mcp_server.py`, `sqlite3`.
* **Current Maturity**: Production Ready (v0.1.9).
* **Future Potential**: Support remote MCP payloads over standard JSON-RPC HTTP transport.

#### Feature 2: Dual-Phase Autonomous Scheduler (`hermit_daemon.py`)
* **Purpose**: Prevents queue starvation and single-skill priority monopolization by alternating between exploration of untouched functions and exploitation of performance bottlenecks.
* **Inputs**: `active_skills` database metrics (latency, complexity, merge counts, consecutive failure counts).
* **Outputs**: Target skill selected for next optimization cycle with designated strategy mode:
  * **Phase 1**: Target untouched skills (0 merges) sorted by optimization headroom (`latency × complexity`).
  * **Phase 2**: Target high-latency bottleneck skills with a maximum consecutive attempts cap (`MAX_CONSECUTIVE = 3`).
* **Dependencies**: `hermit_daemon.py`, `hermit_memory.db`.
* **Current Maturity**: Production Ready (v0.1.9).
* **Future Potential**: Integrate dynamic reinforcement learning for adaptive phase ratio switching.

#### Feature 3: RAM-Disk Isolated Sandbox Harness (`sandbox.py`)
* **Purpose**: Executes untrusted or candidate python code in an isolated 32MB `tmpfs` RAM disk with strict virtual memory, CPU time, and AST safety bounds.
* **Inputs**: Candidate code file path, test parameters, CPU time limit (30s), memory bound (`RLIMIT_AS`).
* **Outputs**: `SandboxResult` object containing execution exit code, duration (ms), exact grandchild process peak RSS (KB), stdout, and stderr.
* **Dependencies**: `sandbox.py`, `resource`, `psutil`, `ast`.
* **Current Maturity**: Production Ready (v0.1.9).
* **Future Potential**: Add containerized Docker or PRoot sandbox fallback layer for non-Linux hosts.

---

### 2. Specialized Mutator Engine Features

#### Feature 4: AST Mathematical Mutator (`math_mutator.py`)
* **Purpose**: Applies deterministic mathematical AST transformations to optimize numeric computation routines.
* **Inputs**: Python source code AST containing numeric or algebraic logic.
* **Outputs**: Transformed AST with constant folding, expression simplification, and closed-form math substitutions.
* **Dependencies**: `math_mutator.py`, `ast`.
* **Current Maturity**: Production Ready (Tested via `test_math_mutator.py` & `test_math_integration.py`).

#### Feature 5: Quantum-Classical QUBO Mutator (`qubo_mutator.py`)
* **Purpose**: Replaces $O(N^2)$ global quadratic energy updates with $O(N)$ local bitwise spin-flip delta calculations.
* **Inputs**: Quadratic Unconstrained Binary Optimization (QUBO) matrix logic and binary vector routines.
* **Outputs**: Optimized bitwise state update routines.
* **Dependencies**: `qubo_mutator.py`, `ast`.
* **Current Maturity**: Production Ready (Tested via `test_qubo_mutator.py` & `test_qubo_integration.py`).

---

### 3. Inventory of Core Active Skills (v0.1.9 Payload)

| Skill Name | Version / Merges | Primary Functionality | Baseline Status |
| :--- | :---: | :--- | :--- |
| `hex_search` | v75 | Binary pattern search and memory buffer scanning | Verified & Benchmark Frozen |
| `scan_allowlist` | v52 | IP / hash allowlist verification and matching | Verified & Benchmark Frozen |
| `parse_ip_port` | v37 | Socket address parsing and validation | Verified & Benchmark Frozen |
| `eval_cond` | v21 | Rule evaluation and conditional AST dispatching | Verified & Benchmark Frozen |
| `generate_hexdump` | v7 | Binary data formatting and string rendering | Verified |
| `search_disk_timeline` | v2 | Regex-compiled file timeline log scanning | Verified |
| `analyze_thoughts` | v2 | Token estimation and bitwise text analytics | Verified |
