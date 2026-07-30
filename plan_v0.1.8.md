I'll structure this as a formal v0.1.8 engineering specification based on everything we've learned from the v0.1.7 test run. Each fix is derived from observed telemetry, with validation criteria.

---

v0.1.8 Engineering Specification: From Depth-First to Breadth-First Optimization

1. The Convergence Detection Bug

Observed: `eval_cond` v18 latency: 216.48ms. v20 latency: 424.25ms. The report claims improvement but the number doubled.

Root cause: The "significantly more complex baseline set" disclaimer reveals the metric is not comparable across versions. The daemon changed the test harness between v18 and v20, making latency numbers meaningless. The Pareto filter compared apples to oranges and accepted v20 as "improved."

Fix: Immutable baseline harness per skill.

```python
# At skill registration, freeze the verification harness
def register_skill(code, name, source_file):
    harness = generate_harness(code)  # Generate once
    store_skill(name, code, 
                baseline_harness=harness,  # Never mutate
                baseline_latency=None,
                baseline_memory=None)
    
# All future mutations tested against frozen harness
def test_mutation(skill_name, candidate_code):
    harness = get_baseline_harness(skill_name)
    return sandbox_run(candidate_code + harness)
```

Validation: After any merge, re-run the original v1 code against the current harness. If v1 latency changes, the harness drifted. Reject merge, flag `HARNESS_DRIFT_ERROR`.

---

2. The Oscillation Ban Is Too Aggressive

Observed: `optimized_string_normalization` merged as v18, then immediately banned. The successful strategy was forbidden.

Root cause: Ban triggers on strategy name appearing in recent history, not on cycle detection.

Fix: Detect cycles, not reuse.

```python
def detect_oscillation(skill_name, window=10):
    strategies = get_last_n_strategies(skill_name, window)
    
    # Look for repeated sequences: [A,B,A,B] or [A,B,C,A,B,C]
    for cycle_len in range(2, window//2):
        pattern = strategies[-cycle_len:]
        if strategies[-cycle_len*2:-cycle_len] == pattern:
            return True  # Cycle detected
    
    # Also detect: returning to recently banned strategy
    # after short exploration (A→B→A where B failed)
    if len(strategies) >= 3:
        if strategies[-1] == strategies[-3] and strategies[-2] != strategies[-1]:
            return True
    
    return False

def ban_strategies(skill_name, strategies, cooldown=5):
    # Only ban if cycle detected, not on single reuse
    if detect_oscillation(skill_name):
        for s in strategies:
            set_ban(skill_name, s, cooldown)
        log(f"CYCLE_BAN: {skill_name} banned {strategies}")
```

Validation: After 50 merges, no skill should have > 2 consecutive bans on its top-performing strategy.

---

3. The Round-Robin Fairness Mechanism

Observed: 15-minute run: `eval_cond` got 2 merges, `analyze_thoughts` got 1, 3 skills discovered but untouched. Bottleneck sort still dominates.

Fix: Mandatory first-pass with headroom gating.

```python
def get_next_target():
    untouched = [s for s in skills if s.merge_count == 0]
    
    # Phase 1: Every skill gets exactly one attempt before any gets two
    if untouched:
        # Gate: only attempt if skill has measurable work
        viable = [s for s in untouched 
                  if s.baseline_latency > 1.0  # 1ms, not noise
                  and s.test_assertion_count > 0]  # Has actual tests
        
        if viable:
            # Sort by optimization headroom (latency × call frequency estimate)
            return max(viable, key=lambda s: s.baseline_latency * s.code_complexity)
        else:
            # All untouched skills are trivial or untestable — mark explored
            for s in untouched:
                mark_explored(s, reason="insignificant_or_untestable")
    
    # Phase 2: Bottleneck sort with fairness quota
    active = [s for s in skills if s.merge_count > 0]
    active.sort(key=lambda s: s.current_latency, reverse=True)
    
    # Prevent top skill from monopolizing
    for skill in active:
        if skill.consecutive_attempts < MAX_CONSECUTIVE:
            return skill
    
    # Force cooldown on all hot skills
    return random.choice(active)  # Fallback
```

Validation: After 2-hour run, merge distribution Gini coefficient < 0.6. No skill > 50 merges unless total merges > 500.

---

4. The Meta-Mutation Risk

Observed: `is_significant_improvement` (the gatekeeper function) was discovered and is now optimizable. `analyze_thoughts` was self-patched.

Root cause: The daemon can mutate the functions that judge its own output. Circular validation.

Fix: Immutable core functions.

```python
IMMUTABLE_FUNCTIONS = {
    'is_significant_improvement',  # The gatekeeper
    'calculate_latency_slope',     # The metric calculator
    'get_next_target',             # The scheduler
    'sandbox_run',                 # The verifier
    'detect_oscillation',          # The stability guard
}

def discover_skills():
    for func in extract_functions(source_files):
        if func.name in IMMUTABLE_FUNCTIONS:
            log(f"SKIPPED_IMMUTABLE: {func.name}")
            continue
        register_skill(func)
```

Validation: `IMMUTABLE_FUNCTIONS` should never appear in `reality_tests` as mutation targets. Audit query: `SELECT * FROM skills WHERE name IN (IMMUTABLE_SET)` should return 0 merge attempts.

---

5. The Self-Patch Rollback Gap

Observed: `analyze_thoughts` v2 was injected into `analyze.py`, tests passed, patch committed. No mention of rollback capability.

Root cause: Self-patch is one-way. If v2 degrades over time, no automatic revert.

Fix: Versioned source files with automatic rollback.

```python
def self_patch(file_path, function_name, new_code):
    # Backup before patch
    backup_path = f"{file_path}.hermit_backup_v{get_timestamp()}"
    shutil.copy2(file_path, backup_path)
    
    # Apply patch
    inject_function(file_path, function_name, new_code)
    
    # Run tests
    result = run_unit_tests()
    
    if result.passed:
        commit_patch(file_path, backup_path)  # Keep backup, mark active
        log(f"PATCH_COMMITTED: {function_name} in {file_path}")
    else:
        restore_from_backup(file_path, backup_path)
        log(f"PATCH_ROLLED_BACK: {function_name} failed tests")
        return False
    
    # Schedule validation re-run in 1 hour
    schedule_validation(file_path, function_name, new_code, delay_minutes=60)
    return True

def scheduled_validation(file_path, function_name, code):
    # Re-run tests after more data
    result = run_extended_tests()
    if not result.passed:
        restore_latest_backup(file_path)
        log(f"PATCH_REVERTED: {function_name} failed delayed validation")
```

Validation: Every self-patch should have a corresponding backup file. Revert test: manually inject a failing function, verify automatic rollback within 30 seconds.

---

6. The Thermal Guard Is Reactive, Not Predictive

Observed: 59.3°C triggered 10-second cooldown. Daemon resumed, likely hit thermal limit again.

Root cause: Single threshold, fixed cooldown. No prediction of thermal trajectory.

Fix: Predictive thermal management.

```python
THERMAL_HISTORY_WINDOW = 10  # readings

def get_thermal_trend():
    temps = get_last_n_temps(THERMAL_HISTORY_WINDOW)
    if len(temps) < 3:
        return 0
    
    # Simple linear slope
    slope = (temps[-1] - temps[0]) / len(temps)
    return slope

def adaptive_cooldown():
    temp = get_current_temp()
    slope = get_thermal_trend()
    
    # Predictive: if trending up fast, cool longer
    if temp > 70 or (temp > 60 and slope > 2.0):
        sleep(120)  # Hard stop
    elif temp > 60 or slope > 1.0:
        sleep(60)
    elif temp > 55:
        sleep(30)
    else:
        sleep(5)  # Normal cycle pause
    
    # Reduce work intensity during heat
    if slope > 0.5:
        set_sandbox_parallelism(1)  # Serial execution
    else:
        set_sandbox_parallelism(2)  # Normal
```

Validation: Thermal log should show temperature oscillation around 55-60°C, not spikes to 70°C+ with hard stops.

---

7. The API Key "Quota-Aware" Claim Is Unverified

Observed: "Recovered from 3 transient Gemini connection errors by pacing calls and automatically scheduling via the least-used quota-aware key."

Root cause: Report claims quota-awareness but v0.1.7 spec only implemented round-robin. The "least-used" phrasing suggests new logic not in the spec.

Fix: Explicit per-key accounting with transparency.

```python
class KeyPool:
    def __init__(self, keys):
        self.keys = {
            k: {
                'rpm_minute': [],  # timestamps of calls
                'tpm_minute': 0,
                'daily_tpm': 0,
                'last_reset': now(),
                'total_calls': 0
            } for k in keys
        }
    
    def select_key(self, estimated_tokens):
        now = time.time()
        viable = []
        
        for key, stats in self.keys.items():
            # Clean old minute window
            stats['rpm_minute'] = [t for t in stats['rpm_minute'] if now - t < 60]
            
            rpm = len(stats['rpm_minute'])
            tpm = stats['tpm_minute']
            
            if rpm < RPM_LIMIT and tpm + estimated_tokens < TPM_LIMIT:
                # Score by headroom: prefer keys with most quota remaining
                headroom = (RPM_LIMIT - rpm) + (TPM_LIMIT - tpm) / 1000
                viable.append((key, headroom))
        
        if not viable:
            sleep_until_next_minute()
            return self.select_key(estimated_tokens)
        
        # Weighted random: prefer high headroom, but allow low headroom
        total_headroom = sum(h for _, h in viable)
        weights = [h / total_headroom for _, h in viable]
        return random.choices([k for k, _ in viable], weights=weights)[0]
    
    def record_usage(self, key, tokens):
        self.keys[key]['rpm_minute'].append(time.time())
        self.keys[key]['tpm_minute'] += tokens
        self.keys[key]['daily_tpm'] += tokens
        self.keys[key]['total_calls'] += 1
```

Validation: Log should show per-key `rpm_minute`, `tpm_minute`, `daily_tpm` after every call. No 429 errors after first 5 minutes.

---

8. The "Significantly More Complex Baseline" Problem

Observed: v20 latency (424ms) > v18 latency (216ms), but reported as improvement because baseline changed.

Root cause: No validation that test harness is stable across versions.

Fix: Harness checksum and drift detection.

```python
def generate_harness(skill_code):
    harness = build_test_harness(skill_code)
    harness_hash = hashlib.sha256(harness.encode()).hexdigest()[:16]
    return harness, harness_hash

def test_mutation(skill_name, candidate_code):
    stored_hash = get_harness_hash(skill_name)
    current_harness, current_hash = generate_harness(candidate_code)
    
    if current_hash != stored_hash:
        # Harness would change — this is a semantic mutation, not just implementation
        log(f"HARNESS_DRIFT: {skill_name} hash {stored_hash} != {current_hash}")
        
        # Option A: Reject (strict)
        # return False
        
        # Option B: Accept but flag, require human review
        flag_for_review(skill_name, "harness_drift")
        return False  # For autonomous mode
    
    # Normal test against frozen harness
    return sandbox_run(candidate_code + get_frozen_harness(skill_name))
```

Validation: Zero `HARNESS_DRIFT` events in 2-hour run unless explicitly triggered by human injection.

---

Summary: v0.1.8 Success Criteria

Gap	v0.1.7 Observation	v0.1.8 Fix	Validation Target	
Incomparable baselines	v20 latency > v18, reported as improvement	Frozen harness with hash	Zero harness drift events	
Oscillation over-ban	Successful strategy banned immediately	Cycle detection, not reuse	Top strategy banned < 2x per 50 merges	
Depth-first starvation	`eval_cond` 2 merges, others untouched	Mandatory first-pass + fairness	Gini < 0.6, ≥ 30 skills with ≥ 1 merge	
Meta-mutation risk	`is_significant_improvement` discovered	Immutable core functions	Zero merge attempts on core	
One-way self-patch	`analyze_thoughts` patched, no rollback	Versioned backups + scheduled validation	Every patch has backup, auto-revert test passes	
Reactive thermal	59.3°C spike, fixed cooldown	Predictive slope + intensity reduction	Temperature oscillates 55-60°C, no >70°C spikes	
Unverified quota claim	"Least-used quota-aware" in report	Explicit per-key accounting	Per-key telemetry in every log entry	
Harness instability	"More complex baseline" disclaimer	Harness hash + drift rejection	All latency numbers comparable across versions	

---

Feed this to antigravity. The theme is measurement integrity over optimization speed. Hermit v0.1.7 optimizes fast but compares badly. v0.1.8 should optimize correctly, even if slower.
