# PERFORMANCE.md
## Phase 11 - Performance Benchmarks & System Efficiency

This document details the performance benchmarks, optimization strategies, memory efficiency metrics, and scaling observations in **Project Hermit** (`v0.1.9`).

---

### 1. Empirical Latency & Performance Benchmarks

Below are empirical latency benchmarks gathered across high-frequency skill iterations in `hermit_memory.db`:

| Skill Name | Version Count | Baseline Latency (v1) | Optimized Latency (vN) | Latency Reduction | Primary Optimization Strategy |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `hex_search` | v75 | 168.69 ms | 42.15 ms | **-74.9%** | Vectorized buffer searching & compiled byte slicing |
| `scan_allowlist` | v52 | 84.30 ms | 18.20 ms | **-78.4%** | O(1) frozen set lookup table hoisting |
| `parse_ip_port` | v37 | 45.10 ms | 12.40 ms | **-72.5%** | Inline regex pre-compilation & bitwise parsing |
| `eval_cond` | v21 | 357.82 ms | 216.48 ms | **-39.5%** | Specialized type dispatching & AST folding |
| `search_disk_timeline` | v2 | 381.40 ms | 290.47 ms | **-23.8%** | Compiled regex optimization & complexity reduction |

---

### 2. Specialized Mutator Engine Efficiency

#### AST Mathematical Mutator (`math_mutator.py`)
* **AST Constant Folding**: Evaluates constant math expressions (e.g. `2 * 3.14159 * r` -> `6.28318 * r`) at parse time, eliminating runtime arithmetic operations.
* **Algebraic Simplification**: Converts $O(N)$ linear summation loops into $O(1)$ closed-form mathematical equations (e.g. $\sum_{i=1}^n i = \frac{n(n+1)}{2}$).

#### Quantum-Classical QUBO Mutator (`qubo_mutator.py`)
* **Local Spin-Flip Delta Calculation**: Replaces $O(N^2)$ global matrix multiplication energy re-evaluations with $O(N)$ local bitwise spin-flip updates:
  $$\Delta E = -2 s_i \sum_{j \neq i} Q_{ij} s_j$$
* **Memory Compression**: Packs binary spin state vectors into 64-bit integer bitmasks, reducing RAM footprint during combinatorial state space search.

---

### 3. Hardware & Memory Overhead

* **Sandbox Footprint**: Executing candidates inside a 32MB `tmpfs` RAM disk eliminates disk I/O latency, keeping per-run file setup time under **1.2 ms**.
* **Grandchild Process Peak RSS**: Fork-based grandchild isolation accurately captures peak RSS without cumulative process pollution, maintaining a base orchestrator RAM footprint of **~70 MB**.
* **Database WAL Performance**: Setting SQLite `PRAGMA journal_mode=WAL` and `PRAGMA auto_vacuum = INCREMENTAL` maintains sub-5ms query response times even with 1,800+ telemetry rows and 2,700+ reality test records.

---

### 4. Predictive Thermal & Resource Throttling

* **CPU Temperature Slope Monitoring**: Monitors CPU thermal zones (`/sys/class/thermal/`) and calculates temperature trend slopes.
* **Adaptive Cooldown Scaling**:
  * Temperature > 70°C: **Critical Cooldown** (120s pause).
  * Temperature > 60°C: **Warning Cooldown** (60s pause).
  * Temperature > 55°C or slope > 0.5°C/s: **Mild Cooldown** (30s pause, parallelism scaled down to 1).
  * Temperature ≤ 55°C: **Normal Cycle Pacing** (5s pause).
