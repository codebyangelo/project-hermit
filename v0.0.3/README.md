# Project Hermit v0.0.3 - Adversarial QA Auditing & Regression Checking

Version `v0.0.3` hardens Project Hermit's evolutionary steps by introducing automated adversarial testing to prevent logical regressions in generated code.

## Core Features
1. **Adversarial QA Agent (`orchestrator.py`):**
   * Before applying any mutation, the QA Auditor Agent is called to analyze the baseline skill logic.
   * Generates 3-5 aggressive boundary assert statements targeting empty inputs, boundary cases, mismatched datatypes, or edge conditions.

2. **Self-Verification Validation:**
   * Runs the baseline code against the newly generated adversarial assertions first. If the baseline fails, the test is rejected as a hallucination, avoiding pipeline deadlocks.
   * Compiles verified assertions into the `adversarial_tests` table.

3. **Cumulative Regression Prevention:**
   * Future mutations must pass both the default verification harness AND all historically accumulated adversarial test suites for that skill before being considered for merging.
