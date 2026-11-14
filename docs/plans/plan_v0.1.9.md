honest scorecard from kimi

Dimension	Grade	Notes	
Queue fairness	B+	Works, but cost-per-merge rising	
Measurement integrity	C+	Harness fixed, memory still broken	
Oscillation handling	D	Success punishment, not cycle detection	
Self-patch safety	B	Rollback exists, not tested live	
Thermal management	B	Implemented, not stress-tested	
API resilience	A	Quota-aware, balanced, no storms	
Downstream testing	A	43 edges, regression tests pass	
Legibility	B+	You can explain merges, but timezone + memory bug need docs	


---

v0.1.9 Engineering Specification: Measurement Integrity & System Hardening

---

1. Oscillation Detection: Fix the Success-Punishment Bug

Problem: v0.1.8 counts all-time strategy appearances. Every successful merge triggers a ban because previous runs accumulated enough hits.

Evidence: `eval_cond` v17→v20: each merge immediately banned. Not cycles — just repeated use.

Fix: True cycle detection with recency window.

```python
def detect_oscillation(skill_name, window=6):
    """
    Detect A-B-A-B or A-B-C-A-B-C patterns in recent merges.
    Count-only bans are disabled.
    """
    strategies = get_last_n_strategies(skill_name, window)
    if len(strategies) < 4:
        return False, []
    
    # Check for period-2 cycles: A-B-A-B
    for period in [2, 3]:
        if len(strategies) >= period * 2:
            first = strategies[-period*2:-period]
            second = strategies[-period:]
            if first == second:
                return True, list(set(first))
    
    # Check for return-after-short-exploration: A at vN, B at vN+1, A at vN+2
    if len(strategies) >= 3:
        if strategies[-1] == strategies[-3] and strategies[-2] != strategies[-1]:
            # Only ban if this exact flip happened before in window
            flips = [(s[i], s[i+1], s[i+2]) 
                    for i in range(len(s)-2) 
                    if s[i] == s[i+2] != s[i+1]]
            if len(flips) >= 2:  # Seen this flip pattern before
                return True, [strategies[-1], strategies[-2]]
    
    return False, []

def ban_strategies(skill_name, strategies, cooldown=5):
    is_cycle, to_ban = detect_oscillation(skill_name)
    if not is_cycle:
        return  # Do NOT ban on count alone
    
    for s in to_ban:
        set_ban(skill_name, s, cooldown)
    log(f"CYCLE_BAN: {skill_name} banned {to_ban} for {cooldown} attempts")
```

Validation: After 50 merges on any skill, no ban should trigger unless the exact sequence A-B-A-B or A-B-C-A-B-C appears in the last 6 merges.

---

2. Memory Measurement: Replace `RUSAGE_CHILDREN`

Problem: `RUSAGE_CHILDREN` returns cumulative peak across all terminated children. Difference is zero if current child uses less than previous peak.

Evidence: All merges show `RAM: 0.0KB`. Pareto filter treats memory as non-discriminative.

Fix: Per-process peak RSS using `psutil`.

```python
import psutil
import subprocess

def measure_sandbox(code, timeout=10):
    proc = subprocess.Popen(
        [sys.executable, '-c', code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    peak_rss_kb = 0
    try:
        # Poll memory while process runs
        p = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                mem = p.memory_info().rss / 1024  # KB
                peak_rss_kb = max(peak_rss_kb, mem)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            time.sleep(0.01)  # 10ms sampling
        
        stdout, stderr = proc.communicate(timeout=timeout)
        
    except subprocess.TimeoutExpired:
        proc.kill()
        peak_rss_kb = -1  # Signal timeout
        stdout, stderr = b'', b''
    
    return {
        'peak_rss_kb': peak_rss_kb,
        'returncode': proc.returncode,
        'stdout': stdout,
        'stderr': stderr,
        'runtime_ms': measure_runtime(proc)  # existing
    }
```

Validation: After fix, no merge should show 0 KB for non-trivial functions. Distribution must show variance: min > 0, max > 1000 for buffer-heavy skills.

Sanity check: If `peak_rss_kb < 1` for a function that allocates buffers, flag `MEASUREMENT_ANOMALY` and reject merge.

---

3. Pareto Scoring: Hierarchical, Weighted, Domain-Aware

Problem: Additive scoring `latency + memory + complexity` treats dimensions as interchangeable. `eval_cond` v19 merged despite 2× latency because complexity dropped 74%.

Evidence: v17: 216.48ms, 2698 chars. v19: 424.25ms, 709 chars. Merged because composite score improved.

Fix: Hierarchical Pareto with DFIR-aware weights.

```python
def pareto_dominates(candidate, baseline):
    """
    Hierarchical: latency is gate, memory is guard, complexity is tiebreaker.
    """
    # Gate 1: Latency must improve or stay within noise (5%)
    if candidate['latency_ms'] > baseline['latency_ms'] * 1.05:
        return False, "latency_regression"
    
    # Gate 2: Memory must not regress beyond 10%
    if candidate['memory_kb'] > baseline['memory_kb'] * 1.10:
        return False, "memory_regression"
    
    # Gate 3: At least one dimension must improve significantly (>5%)
    latency_improved = candidate['latency_ms'] < baseline['latency_ms'] * 0.95
    memory_improved = candidate['memory_kb'] < baseline['memory_kb'] * 0.95
    complexity_improved = candidate['complexity'] < baseline['complexity'] * 0.95
    
    if not any([latency_improved, memory_improved, complexity_improved]):
        return False, "insignificant_improvement"
    
    # Tiebreaker: minimize complexity among candidates that pass gates
    return True, "accepted"

# Alternative: weighted scoring for cases where gates are too strict
def weighted_score(candidate, weights=None):
    if weights is None:
        weights = {
            'latency': 10.0,      # DFIR: speed matters most
            'memory': 2.0,        # Constrained hardware: memory matters
            'complexity': 0.5     # Maintainability: minor concern
        }
    
    # Normalize each dimension against baseline
    latency_ratio = candidate['latency_ms'] / baseline['latency_ms']
    memory_ratio = candidate['memory_kb'] / baseline['memory_kb'] 
    complexity_ratio = candidate['complexity'] / baseline['complexity']
    
    score = (latency_ratio * weights['latency'] +
             memory_ratio * weights['memory'] +
             complexity_ratio * weights['complexity'])
    
    return score  # Lower is better
```

Validation: Re-run v17→v19 decision. v19 should be rejected under hierarchical gates (latency regression). Under weighted scoring, v19 should score worse than v17.

Proactive: Make weights configurable per skill class. `hex_search` (buffer-heavy) might weight memory higher. `eval_cond` (called frequently) weights latency higher.

---

4. Timezone Unification: UTC Everywhere

Problem: Logs use local time (UTC+2), database uses UTC. Antigravity misreported events as separate.

Fix: Single source of truth.

```python
import datetime

# All timestamps stored as UTC ISO format
def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

# Display conversion only at UI layer
def display_local(ts_utc, tz_offset=2):
    dt = datetime.datetime.fromisoformat(ts_utc)
    return dt.astimezone(datetime.timezone(datetime.timedelta(hours=tz_offset)))
```

Validation: Query `SELECT DISTINCT timezone FROM logs` should return only `UTC`. No local time strings in database.

---

5. Cost-Per-Merge Monitoring: Fairness Quota Economics

Problem: Tokens/merge rose from 23K to 91K. Phase 1 on untouched skills is expensive.

Evidence: `search_disk_timeline` took 39 API calls for 1 merge. Complex untouched functions require many synthesis iterations.

Fix: Per-skill cost tracking with budget gates.

```python
class SkillBudget:
    def __init__(self):
        self.max_tokens_per_skill = 500000  # Hard cap
        self.max_calls_per_skill = 100      # Hard cap
        self.min_improvement_per_token = 0.0001  # ms saved per token
    
    def can_attempt(self, skill_name):
        stats = get_skill_stats(skill_name)
        if stats['total_tokens'] > self.max_tokens_per_skill:
            log(f"BUDGET_EXHAUSTED: {skill_name} at {stats['total_tokens']} tokens")
            mark_explored(skill_name, reason="token_budget_exhausted")
            return False
        
        if stats['total_calls'] > self.max_calls_per_skill:
            log(f"CALL_BUDGET_EXHAUSTED: {skill_name}")
            mark_explored(skill_name, reason="call_budget_exhausted")
            return False
        
        return True
    
    def record_attempt(self, skill_name, tokens_used, latency_delta):
        # Track efficiency: are we getting improvement per token?
        if tokens_used > 0:
            efficiency = latency_delta / tokens_used
            if efficiency < self.min_improvement_per_token and stats['merge_count'] > 0:
                log(f"LOW_EFFICIENCY: {skill_name} {efficiency:.6f} ms/token")
```

Validation: After 2-hour run, no skill should exceed 500K tokens unless it has > 10 merges. Average efficiency should be logged and trended.

---

6. Proactive Hardening: Latent Risks from v0.1.8 Telemetry

6a. Database Corruption Detection

Risk: SQLite WAL mode is robust, but phone power loss or proot crash can corrupt.

Fix:

```python
# Startup integrity check
def verify_database():
    try:
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] != 'ok':
            log(f"DATABASE_CORRUPTION: {result[0]}")
            restore_from_backup()
    except sqlite3.DatabaseError as e:
        log(f"DATABASE_ERROR: {e}")
        restore_from_backup()

# Periodic backup every 30 minutes
def schedule_backup():
    backup_path = f"hermit_memory_backup_{now_utc()}.db"
    cursor.execute(f"VACUUM INTO '{backup_path}'")
```

6b. Sandbox Escape Hardening

Risk: v0.1.8 reported 0 escape attempts, but sandbox is basic process isolation.

Fix:

```python
# Resource limits
import resource

def set_sandbox_limits():
    # 512MB virtual memory
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    # 30 second CPU time
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    # No file writes outside sandbox
    # (Implemented via chroot or seccomp where available)
```

6c. LLM Output Poisoning

Risk: Gemini could generate code that passes tests but contains backdoors or data exfiltration.

Fix:

```python
# Static analysis before sandbox
import ast

def analyze_code_safety(code):
    tree = ast.parse(code)
    
    # Block dangerous imports
    dangerous = ['os.system', 'subprocess', 'socket', 'urllib', 'requests']
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in dangerous:
                    return False, f"blocked_import: {alias.name}"
        if isinstance(node, ast.Call):
            # Detect network calls, file writes outside sandbox
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ['system', 'popen', 'call']:
                    return False, f"blocked_call: {node.func.attr}"
    
    return True, "passed"
```

6d. Silent Stagnation Detection

Risk: System runs for hours with no merges, burning tokens. No automatic flag.

Fix:

```python
def check_stagnation():
    last_merge = get_last_merge_time()
    hours_since_merge = (now_utc() - last_merge).total_seconds() / 3600
    
    if hours_since_merge > 1:
        log(f"STAGNATION_WARNING: No merges in {hours_since_merge:.1f} hours")
        # Options: pause, notify, or force exploration of random skills
        force_exploration_mode()
```

---

7. Skill Classification: Don't Optimize Everything the Same Way

Proactive: Not all skills should use the same prompt, scoring, or strategy set.

```python
SKILL_CLASSES = {
    'parser': {
        'strategies': ['regex_compilation', 'dispatch_table', 'short_circuit'],
        'weights': {'latency': 10, 'memory': 3, 'complexity': 1},
        'max_versions': 50
    },
    'search': {
        'strategies': ['memoryview', 'native_find', 'bitmap_index'],
        'weights': {'latency': 10, 'memory': 10, 'complexity': 0.5},
        'max_versions': 100
    },
    'io_bound': {
        'strategies': ['async_io', 'buffer_pool', 'mmap'],
        'weights': {'latency': 5, 'memory': 2, 'complexity': 1},
        'max_versions': 20
    }
}

def classify_skill(skill_name, code):
    # Heuristic: analyze code patterns
    if 're.' in code or 'parse' in skill_name:
        return 'parser'
    if 'find' in skill_name or 'search' in skill_name:
        return 'search'
    if 'open(' in code or 'read(' in code:
        return 'io_bound'
    return 'general'
```

---

v0.1.9 Success Criteria

Fix	Validation Target	
True cycle detection	Zero count-based bans; only A-B-A-B triggers	
Per-process RSS	No 0 KB merges; variance in memory distribution	
Hierarchical Pareto	v19-type latency regression rejected	
UTC everywhere	Single timezone in all stores	
Cost tracking	No skill > 500K tokens without > 10 merges	
DB integrity check	Startup verification, 30-min backups	
Sandbox hardening	Resource limits enforced, dangerous imports blocked	
Stagnation detection	Flag if no merge in 1 hour	
Skill classification	Each skill tagged, prompt/strategy set adapted	

---
