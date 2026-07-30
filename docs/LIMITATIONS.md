# LIMITATIONS.md
## Phase 14 - Technical Debt & System Limitations

This document catalogs the known issues, technical debt, platform constraints, and unsupported features in **Project Hermit** (`v0.1.9`).

---

### 1. Known Technical Debt & Architectural Gaps

1. **Token Cost Escalation on Complex Untouched Functions**:
   * *Observation*: Phase 1 scheduling targets complex untouched functions. LLM synthesis attempts on intricate algorithms frequently fail verification tests during initial iterations, driving average synthesis costs up to **~91,600 tokens per merge**.
   * *Impact*: High API token consumption during early exploration phases.
   * *Mitigation in v0.1.9*: Added `skill_budgets` token gating to block attempts exceeding 500,000 tokens on un-merged functions unless explicitly overridden.

2. **Linux-Specific RAM Disk & Resource Limits**:
   * *Observation*: `sandbox.py` relies directly on Linux-specific kernel features (`mount -t tmpfs`, `resource.RLIMIT_AS`, `resource.RLIMIT_CPU`, `/proc` filesystem checks).
   * *Impact*: The sandbox execution engine cannot run natively on Windows or macOS hosts without containerization (WSL2, Docker, or PRoot).

3. **Timezone Discrepancy in Historical Logs**:
   * *Observation*: Log entries in earlier versions (`v0.1.7`/`v0.1.8`) were recorded in local server time (UTC+2), whereas database records were stored in UTC.
   * *Mitigation in v0.1.9*: Unified all timestamps in logs, database records, and thought ledgers to standard UTC.

---

### 2. Current Unsupported Features

* **Multi-Language Payload Support**: Project Hermit currently supports Python payload mutation only. C/C++, Rust, or JavaScript payload optimization is not implemented.
* **Remote Microservice MCP Payloads**: The dynamic MCP payload currently operates via in-process module hot-reloading (`importlib.reload`). Distributed network payload mutation via gRPC / HTTP transport is not supported.
* **Unrestricted Host Self-Mutation**: Modifying core host controller functions (`IMMUTABLE_FUNCTIONS`) is strictly forbidden to prevent system instability.
