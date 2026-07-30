# CONTRIBUTING.md
## Contributing Guidelines for Project Hermit

Thank you for your interest in contributing to **Project Hermit**!

---

### Core Development Principles

1. **Evidence First**: All documentation, features, and performance claims must be supported by verifiable code or benchmark evidence in `hermit_memory.db`.
2. **Immutable Host Security**: Never alter functions registered in `IMMUTABLE_FUNCTIONS` (`get_next_target`, `sandbox_run`, `detect_oscillation`, `is_significant_improvement`) without explicit architectural review.
3. **Verification Before Merge**: Every PR or code candidate must pass the baseline verification harness, AST code safety checks (`analyze_code_safety`), and downstream dependency regression tests (`skill_dependencies`).

---

### How to Submit Code Changes

1. **Set Up Development Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install google-genai psutil
   export GEMINI_API_KEY="your-key"
   ```

2. **Run Full System Integration Tests**:
   ```bash
   python3 test_hermit.py
   python3 test_math_mutator.py
   python3 test_qubo_mutator.py
   ```

3. **Submit Your Pull Request**: Ensure all test suites pass cleanly before opening a pull request.
