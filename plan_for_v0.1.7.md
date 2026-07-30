---

v0.1.7 Engineering Specification: Queue Starvation & System Hardening

1. Queue Starvation: The 87/97 Problem

Problem: The bottleneck sort (`AVG(duration_ms) DESC`) creates a priority inversion. Skills with high latency (because they do heavy work) monopolize the mutation queue. Skills with zero merges never get attempted.

Evidence: 87 skills at 0 merges. Top 3 skills consume 83.3% of all merges. `parse_ip_port` overwritten 119 times.

Fix: Implement a fairness quota in `get_bottleneck_skills`.

```python
# Pseudocode for v0.1.7
def get_next_target():
    # 70% of cycles: bottleneck sort (existing behavior)
    if random() < 0.7:
        return get_slowest_passing_skill()
    
    # 20% of cycles: zero-merge skills (new)
    untouched = get_skills_with_zero_merges()
    if untouched:
        return random.choice(untouched)
    
    # 10% of cycles: random skill (exploration)
    return random.choice(all_skills)
```

Validation: After 2-hour run, no skill should have > 50 merges. Minimum 30 skills should have ≥ 1 merge. Gini coefficient of merge distribution should drop from current 0.92 to < 0.6.

---

2. Convergence Detection: Replace `while True`

Problem: No system-level stop condition. Daemon runs until manual kill or resource exhaustion. Per-skill plateau logic (3 failures) just retries with Research Agent.

Evidence: `while True` at daemon.py:227. No cumulative improvement tracking. 2-hour runs are manually timed.

Fix: Implement global convergence detection.

```python
# Track rolling improvement window
IMPROVEMENT_WINDOW_MINUTES = 20
MIN_IMPROVEMENT_THRESHOLD = 0.05  # 5% latency reduction

def should_continue():
    recent_merges = get_merges_last_n_minutes(IMPROVEMENT_WINDOW_MINUTES)
    if not recent_merges:
        return False  # Nothing improving, stop
    
    latency_trend = calculate_latency_slope(recent_merges)
    if latency_trend > -MIN_IMPROVEMENT_THRESHOLD:
        log("Global plateau detected. Initiating graceful shutdown.")
        return False
    
    # Hard bounds
    if total_tokens > TOKEN_BUDGET or runtime_hours > MAX_RUNTIME:
        return False
    
    return True
```

Validation: Daemon should auto-stop within 30 minutes of last meaningful merge. Log should emit `GLOBAL_PLATEAU_SHUTDOWN` event.

---

3. Semantic Stability: Stop the Oscillation

Problem: 100% overwrite rate means no history. `eval_cond` oscillates between strategies. The "final" code is whatever scored last, not what converged.

Evidence: `eval_cond` v1→v17 dropped 329ms→167ms, but strategy cycled regex→short-circuit→dispatch→regex. No rollback to v41 if v42 breaks.

Fix: Implement version retention with divergence detection.

```python
# Keep last N versions, not just active slot
VERSION_RETENTION = 5

def merge_candidate(skill, candidate):
    # Store in version history
    store_version(skill, candidate)
    
    # Check for oscillation: same strategy appearing/disappearing
    recent_strategies = get_last_n_strategies(skill, n=10)
    if detect_cycle(recent_strategies):
        log(f"OSCILLATION_DETECTED: {skill}")
        # Force exploration: ban last 3 strategies for next 5 attempts
        ban_strategies(skill, recent_strategies[-3:], cooldown=5)
    
    # Only overwrite if statistically significant improvement
    if not is_significant_improvement(candidate, active_version, p=0.05):
        log("Merge rejected: improvement below noise threshold")
        return False
    
    set_active(skill, candidate)
```

Validation: No skill should show the same strategy more than twice in a 10-merge window. Database should contain `version_history` table with ≥ 5 entries per active skill.

---

4. Cross-Skill Regression: Dependency-Aware Testing

Problem: Skills tested in isolation. Callers not re-verified. `test_hermit.py` coverage unknown.

Evidence: Explicit warning in report: "If a downstream skill depends on skill A... regression will go unnoticed."

Fix: Build a static dependency graph and trigger downstream verification.

```python
# Build graph at registration time
def register_skill(code, name):
    imports = extract_imports(code)  # regex or ast
    callers = find_skills_calling(name)  # grep all skill code
    store_dependency_edges(name, imports + callers)

def merge_candidate(skill, candidate):
    # Existing: sandbox test skill in isolation
    if not sandbox_test(candidate):
        return False
    
    # New: identify downstream skills
    downstream = get_dependents(skill)
    for dependent in downstream:
        # Patch dependent's code to call candidate, re-run verification
        patched = patch_caller(dependent, skill, candidate)
        if not sandbox_test(patched):
            log(f"REGRESSION: {dependent} broken by {skill} mutation")
            return False
    
    return True
```

Validation: After any merge, `reality_tests` table should show ≥ 1 additional "downstream_regression" test entry. No merge should proceed if any downstream test fails.

---

5. API Key Quota Tracking: Fix the Retry Storm

Problem: Round-robin rotation with no per-key quota tracking. Exhausted keys get retried, causing 429 loops.

Evidence: Report admits: "If one key is completely exhausted, the system will still attempt to use it."

Fix: Implement per-key quota accounting.

```python
class KeyPool:
    def __init__(self, keys):
        self.keys = {k: {'rpm_used': 0, 'tpm_used': 0, 
                        'daily_tpm': 0, 'last_reset': now()} 
                    for k in keys}
    
    def select_key(self):
        viable = [k for k, stats in self.keys.items() 
                 if stats['rpm_used'] < RPM_LIMIT 
                 and stats['tpm_used'] < TPM_LIMIT
                 and stats['daily_tpm'] < DAILY_TPM_CAP]
        
        if not viable:
            sleep_until_next_reset()
            return self.select_key()
        
        # Weighted: prefer least-used
        return min(viable, key=lambda k: self.keys[k]['daily_tpm'])
    
    def record_usage(self, key, tokens):
        self.keys[key]['rpm_used'] += 1
        self.keys[key]['tpm_used'] += tokens
        self.keys[key]['daily_tpm'] += tokens
```

Validation: Zero `429` errors after first 10 minutes of run. All keys should show balanced daily usage within 20% variance.

---

6. Context Retention: Fix the `memoryview.find()` Loop

Problem: `hex_search` fails 66.7% because LLM forgets `memoryview` lacks `.find()`. Context window (last 3 tracebacks) cycles before lesson sticks.

Evidence: 114 `AttributeError` failures on `hex_search`. Research Agent writes "strategy notes" but synthesizer repeats the error.

Fix: Implement persistent negative examples in prompt context.

```python
# In prompt construction
def build_synthesizer_prompt(skill, history):
    # Existing: last 5 mutations, last 3 tracebacks
    base = get_recent_history(skill, mutations=5, tracebacks=3)
    
    # New: permanent anti-patterns for this skill
    anti_patterns = get_persistent_failures(skill, min_occurrences=3)
    # e.g., "DO NOT use .find() on memoryview objects. Use bytes.find() or manual indexing."
    
    # New: global anti-patterns (cross-skill)
    global_anti = get_global_anti_patterns()
    
    return f"""
    {base}
    
    [PERMANENT CONSTRAINTS - Do Not Violate]
    {format_anti_patterns(anti_patterns + global_anti)}
    
    [TASK] Generate 3 variants for {skill}...
    """
```

Validation: `hex_search` fail rate should drop from 66.7% to < 20% within 50 attempts. Anti-patterns table should contain ≥ 1 entry per skill with > 10 failures.

---

7. Storage Hardening: `tmpfs` Sandbox & Log Rotation

Problem: 2,049 sandbox executions write to disk. Logs grow unbounded (5,040+ lines in 80 minutes). No cleanup.

Evidence: Report suggests `tmpfs` but doesn't implement it. Cumulative logs unbounded.

Fix: 
- Mount `sandbox_run` as `tmpfs` (32MB sufficient for Python scripts).
- Implement log rotation: compress logs > 10MB, archive to `.gz`, keep last 3 runs.
- Add `PRAGMA auto_vacuum = INCREMENTAL` to SQLite.

```bash
# Startup check
if ! mountpoint -q sandbox_run; then
    mount -t tmpfs -o size=32M tmpfs sandbox_run
fi
```

Validation: `sandbox_run` should show `tmpfs` in `mount`. Log directory should never exceed 50MB. SQLite file size should stabilize after 1 hour.

---

8. Thermal-Aware Throttling

Problem: Phone thermally throttles. Daemon doesn't adapt. Sandbox latency increases but daemon doesn't know why.

Evidence: Report notes thermal throttling but daemon has no thermal telemetry.

Fix: Read `/sys/class/thermal/thermal_zone*/temp` before each sandbox run. If temp > 65°C, increase sleep between cycles.

```python
def get_thermal_state():
    temps = []
    for zone in glob('/sys/class/thermal/thermal_zone*/temp'):
        try:
            temps.append(int(read(zone)) / 1000)  # millidegree to celsius
        except:
            pass
    return max(temps) if temps else 0

def adaptive_sleep():
    temp = get_thermal_state()
    if temp > 75:
        sleep(60)  # Cool down
    elif temp > 65:
        sleep(30)
    elif temp > 55:
        sleep(10)
    # else: default sleep
```

Validation: Log should contain `THERMAL_THROTTLE` events. No CPU temperature should exceed 80°C for more than 5 consecutive minutes.

---

Summary: v0.1.7 Success Criteria

Gap	Fix	Validation Target	
Queue starvation	Fairness quota	≥ 30 skills with ≥ 1 merge, Gini < 0.6	
No stop condition	Global convergence	Auto-stop within 30 min of plateau	
Oscillation	Version retention + cycle detection	No strategy repeats > 2x in 10 merges	
Cross-skill regressions	Dependency graph + downstream tests	100% downstream coverage on merge	
Retry storms	Per-key quota tracking	Zero 429s after warmup, balanced usage	
Context amnesia	Persistent anti-patterns	`hex_search` fail rate < 20%	
Storage bloat	tmpfs + log rotation	< 50MB log dir, stable SQLite	
Thermal blindness	Thermal-aware sleep	No sustained > 80°C	

---
