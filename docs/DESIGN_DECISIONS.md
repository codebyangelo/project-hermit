# DESIGN_DECISIONS.md
## Phase 4 - Engineering Rationale & Architecture Trade-Offs

This document records the architectural trade-offs, rejected design alternatives, security choices, and performance optimizations made during the development of **Project Hermit**.

---

### 1. Key Engineering Rationale & Trade-Offs

#### Decision 1: Host-Payload Decoupling via Dynamic MCP Server (`dynamic_mcp_server.py`)
* **Context**: Self-evolving code systems need a mechanism to update running functions without corrupting host state.
* **Trade-Off**:
  * *Option A (In-process modification)*: Directly rewrite `orchestrator.py` or host script functions during execution.
  * *Option B (Decoupled Payload with Hot-Reloading)*: Place target skill payloads inside a separate module (`dynamic_mcp_server.py`) and hot-reload via `importlib.reload`.
* **Rationale**: Option B was selected. In-process modification carries high crash risk and invalidates execution state. Decoupling allows hot-reloading target skills cleanly without terminating the orchestrator process.

#### Decision 2: RAM-Disk (`tmpfs`) Sandbox Execution (`sandbox.py`)
* **Context**: Executing thousands of generated Python code candidates creates disk write overhead and risks persistent filesystem contamination.
* **Trade-Off**:
  * *Option A (Direct disk execution)*: Execute candidates in standard subdirectories.
  * *Option B (32MB `tmpfs` RAM Disk Mount)*: Mount `sandbox_run` in RAM disk memory with fallback self-healing checks.
* **Rationale**: Option B was selected. RAM-disk mounting reduces storage I/O latency to sub-millisecond levels and protects SSD storage from thousands of temporary write cycles per run.

#### Decision 3: Fork-Based Grandchild Sandbox Memory Measurement
* **Context**: `resource.RUSAGE_CHILDREN` measures cumulative peak RSS across all past child process executions, resulting in `0.0 KB` RAM usage deltas if a candidate uses less memory than a previous process.
* **Trade-Off**:
  * *Option A (Keep `RUSAGE_CHILDREN`)*: Simple implementation, but produces false `0.0 KB` memory deltas.
  * *Option B (Fork-Based Grandchild Isolation)*: Fork child process and monitor peak RSS of individual process subtrees via `/proc` or `psutil`.
* **Rationale**: Option B was selected in `v0.1.9` to ensure exact, isolated memory measurement per candidate attempt.

---

### 2. Rejected Alternatives & Design Decisions

| Problem Area | Considered Approach | Why Rejected | Final Implemented Solution |
| :--- | :--- | :--- | :--- |
| **Strategy Ban Logic** | Count-based strategy ban (>2 occurrences in DB) | Immediately banned newly merged strategies because historical runs accumulated hits in `version_history`. | Sequence cycle pattern detection (`A-B-A-B` or `A-B-C-A-B-C` over recency window of 6). |
| **Candidate Scoring** | Linear additive sum (`latency + memory + complexity`) | Allowed functions with 2x latency degradation to merge if code complexity dropped significantly. | Hierarchical Pareto scoring (strict latency gate, memory guard, complexity tiebreaker). |
| **Queue Scheduling** | Single bottleneck queue (`AVG(latency) DESC`) | High-latency functions monopolized the queue; 89.6% of skills received 0 merge attempts. | Dual-Phase Scheduling (Phase 1 untouched headroom vs Phase 2 bottleneck with concurrency caps). |
| **API Key Pool** | Round-robin key rotation without budget checks | Retried exhausted keys, leading to rate limit (`429`) loops during heavy LLM synthesis. | Quota-aware key pool tracking RPM, TPM, and daily token limits per key in `api_keys.txt`. |

---

### 3. Security, Isolation & Sandboxing Decisions

1. **Immutable Function Protection (`IMMUTABLE_FUNCTIONS`)**:
   * Critical host looper functions (`get_next_target`, `sandbox_run`, `detect_oscillation`, `is_significant_improvement`) are explicitly registered as immutable. Any attempt to modify or mutate these functions is aborted during discovery.
2. **Pre-Execution Static Safety Analysis (`analyze_code_safety`)**:
   * Evaluates Python candidate ASTs prior to execution. Automatically blocks unsafe imports (`subprocess`, `requests`, `urllib`) and attribute calls (`os.system`, `shutil.rmtree`, `eval`, `exec`).
3. **Resource Bound Enforcement**:
   * Enforces strict execution constraints in `sandbox.py`: `RLIMIT_CPU` capped at 30s, dynamic `RLIMIT_AS` virtual memory limits (Parent VmSize + 512MB), and 32MB `tmpfs` storage bounds.
