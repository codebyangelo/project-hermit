# INSTALL.md
## Phase 6 - Installation & Environment Setup Guide

This document provides complete instructions for setting up, configuring, and verifying **Project Hermit** (`v0.1.9`) on Linux and Unix-like environments.

---

### 1. Prerequisites

Before installing Project Hermit, ensure your environment meets the following requirements:

* **Operating System**: Linux / Unix (Debian/Ubuntu, RHEL/Fedora, or Arch Linux recommended).
* **Python Runtime**: Python 3.10 or higher (Python 3.13 verified).
* **System Utilities**: `gcc` / build essentials, `mount` / `tmpfs` privileges for RAM-disk mounting.
* **Python Packages**:
  * `google-genai` or `google-generativeai` (for LLM synthesis features)
  * `psutil` (for process and memory telemetry)
  * Built-in standard modules: `sqlite3`, `ast`, `resource`, `os`, `sys`, `json`, `math`

---

### 2. Installation & Setup

1. **Clone or Extract the Repository**:
   ```bash
   git clone https://github.com/your-org/project-hermit.git
   cd project-hermit-git/v0.1.9
   ```

2. **Set Up a Virtual Environment** *(Recommended)*:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Required Python Dependencies**:
   ```bash
   pip install google-genai psutil
   ```

4. **Configure API Key**:
   Set your Google Gemini API key as an environment variable:
   ```bash
   export GEMINI_API_KEY="your-actual-api-key"
   ```

---

### 3. Verification & Diagnostic Testing

Verify that the engine, sandbox isolation, database schema, and AST mutators are functioning properly by running the full test suite:

1. **Run Structural Host Verification Test**:
   ```bash
   python3 orchestrator.py --mode shadow_test
   ```

2. **Run Main Integration Test Suite** (Verifies database, sandbox, key management, and self-patch rollbacks):
   ```bash
   python3 test_hermit.py
   ```
   *Expected Output*: `Ran 17 tests in ~6.6s ... OK`

3. **Run Mathematical AST Mutator Tests**:
   ```bash
   python3 test_math_mutator.py
   python3 test_math_integration.py
   ```

4. **Run QUBO Spin-Flip Engine Tests**:
   ```bash
   python3 test_qubo_mutator.py
   python3 test_qubo_integration.py
   ```
