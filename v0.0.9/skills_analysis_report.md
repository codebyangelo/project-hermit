# 📊 Project Hermit: v0.0.8 Skills Analysis & Categorization Report

During the evolution of Project Hermit version `v0.0.8`, the autonomous Discovery Agent scanned multiple repositories in the workspace:
1. `project-hermit` (Self-introspection of CLI and Orchestrator)
2. `project-lobster` (The Agentic Immune System)
3. `project-mantis` (The Autonomous DFIR Agent)

This scan populated the database (`hermit_memory.db`) with **76 active skills** representing a wide variety of domain functions.

This report analyzes what `v0.0.8` achieved with these skills, provides a detailed classification of all 76 skills, and outlines clear guidelines on what to focus on and what to exclude to avoid wasting API tokens and processing cycles in `v0.0.9`.

---

## 🚀 What v0.0.8 Built and Evolved

Before analyzing the baseline skills, it is critical to understand the evolutionary changes that occurred in version `v0.0.8`. 

Three core functions were evolved beyond their base registration (Version 1):

1. **`hex_search` (v74):**
   * **Original State:** A naive string pattern matching loop that scanned memory buffers byte-by-byte.
   * **Current State (v74):** Rewritten into a highly optimized Python-native iterator using `.find()` inside a generator yield loop. It runs up to 100x faster on large byte streams and was stress-tested across dozens of candidates to verify correctness.
2. **`parse_ip_port` (v2):**
   * **Original State:** Used the `struct` module (`struct.pack("<I"...)`) to convert hex-encoded IP addresses from `/proc/net/` files.
   * **Current State (v2):** Optimized by removing the `struct` import entirely. It parses network byte order directly using native python byte manipulation (`bytes.fromhex` and slice notation) and `socket.inet_ntop`.
3. **`generate_hexdump` (v2):**
   * **Original State:** Performed expensive character-by-character checking and lists formatting inside a loop for ASCII displays.
   * **Current State (v2):** Optimized using a pre-computed translation table (`bytes.translate`) to map printable characters and bypass character-by-character checks.
4. **`_normalize_and_decode_args` (v2):**
   * **Original State:** Repetitive inline regular expression compiles and decoding attempts.
   * **Current State (v2):** Pre-compiled the regex pattern (`B64_PATTERN`) globally and optimized the try-except logic for base64 strings, speeding up LOTL detection loops.

The remaining 72 skills are currently registered at **Version 1** and represent the baseline code extracted from the different modules of `project-mantis` and `project-lobster`.

---

## 📂 Categorization & Action Plan for the 76 Skills

To prevent Project Hermit from wasting precious API tokens and sandbox runs on non-bottleneck functions or breaking its own system code, we have classified the 76 skills into **four distinct categories**:

1. **Core DFIR Forensic Carving & Extraction** (KEEP & OPTIMIZE)
2. **Triage, Threat Detection & Sieve Logic** (KEEP & OPTIMIZE)
3. **Data Parsing & General Utilities** (KEEP - Low Priority)
4. **Framework Infrastructure & Internal Control Loop** (AVOID/EXCLUDE)

### 📊 Summary Table

| Category | Skill Count | Primary Source | Evolutionary Action | Focus Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Core DFIR Forensic Carving & Extraction** | 21 | `project-mantis` (MCP, Extractor) | **KEEP & OPTIMIZE** | High impact. These functions parse large file sizes (memory dumps, disks, PCAPs). Any optimization directly translates to huge time savings. |
| **Triage, Threat Detection & Sieve Logic** | 16 | `project-mantis` (Sieve) | **KEEP & OPTIMIZE** | High impact. Executed repeatedly over millions of telemetry rows. Key to reducing threat classification latency. |
| **Data Parsing & General Utilities** | 17 | Both Mantis & Lobster | **KEEP (Low Priority)** | Medium impact. Standard utility functions. Keep in DB as support functions, but do not prioritize for optimization. |
| **Framework Infrastructure** | 22 | `project-hermit`, Mantis/Lobster Orchestrator | **AVOID / EXCLUDE** | Critical risk. Framework-specific glue code (CLI printing, SQLite queries, LLM adapters). Optimizing them risks breaking Hermit's core loop or wasting tokens. |

---

## 🔍 Detailed Skill Directory

Here is the complete inventory of all 76 skills, including their containing file locations (linked to code), versions, and recommended actions.


### 📦 Core DFIR Forensic Carving & Extraction (21 skills)

| Skill Name | Current Version | Source File | Action / Recommendation |
| :--- | :--- | :--- | :--- |
| `_generator` | v1 | [mantis_carve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mantis_carve.py#L45), [mantis_carve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mantis_carve.py#L140), [mantis_carve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mantis_carve.py#L45), [mantis_carve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mantis_carve.py#L140) | **KEEP & OPTIMIZE (High Impact)** |
| `_get_suspicious_vads` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L319), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L319), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L349), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L349) | **KEEP & OPTIMIZE (High Impact)** |
| `carve_and_stream_strings` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L253), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L253), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L367), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L367) | **KEEP & OPTIMIZE (High Impact)** |
| `carve_memory_strings` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L458), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L541), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L541), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L541) | **KEEP & OPTIMIZE (High Impact)** |
| `carve_pid_committed_fallback` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L411), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L494), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L494), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L494) | **KEEP & OPTIMIZE (High Impact)** |
| `classify_image` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L10), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L10), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L10), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L10) | **KEEP & OPTIMIZE (High Impact)** |
| `detect_partition_offset` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L206), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L206), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L320), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L320) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_and_carve_hive` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L221), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L221), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L221), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L221) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_cmdline_linux` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L192), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L192) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_evtx_stream` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L312), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L312), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L426), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L426) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_lnk_stream` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L372), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L372), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L486), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L486) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_malfind_linux` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L205), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L205) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_netscan_linux` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L223), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L223) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_pcap_stream` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L401), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L401), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L515), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L515) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_prefetch_stream` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L342), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L342), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L456), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L456) | **KEEP & OPTIMIZE (High Impact)** |
| `extract_pstree_linux` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L179), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L179) | **KEEP & OPTIMIZE (High Impact)** |
| `get_disk_image` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L283), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L283), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L283), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L283) | **KEEP & OPTIMIZE (High Impact)** |
| `get_memory_image` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L293), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L293), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L293), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L293) | **KEEP & OPTIMIZE (High Impact)** |
| `parse_and_cache` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L75), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L75), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L119), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L119) | **KEEP & OPTIMIZE (High Impact)** |
| `prcarve_registry_map` | v1 | [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/extractor.py#L135), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.3/extractor.py#L135), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.4/extractor.py#L249), [extractor.py](file:////root/home/projects/project-mantis/agent_v0.5.5/extractor.py#L249) | **KEEP & OPTIMIZE (High Impact)** |
| `search_disk_timeline` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L487), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L570), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L570), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L570) | **KEEP & OPTIMIZE (High Impact)** |

### 📦 Triage, Threat Detection & Sieve Logic (16 skills)

| Skill Name | Current Version | Source File | Action / Recommendation |
| :--- | :--- | :--- | :--- |
| `_has_suspicious_lotl_args` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L133), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L133), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L162), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L190) | **KEEP & OPTIMIZE (High Impact)** |
| `_is_anomalous_path` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L106), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L106), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L135), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L135) | **KEEP & OPTIMIZE (High Impact)** |
| `_is_masquerading` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L124), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L124), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L153), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L153) | **KEEP & OPTIMIZE (High Impact)** |
| `_is_private_or_reserved` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L64), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L64), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L93), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L93) | **KEEP & OPTIMIZE (High Impact)** |
| `_normalize_and_decode_args` | v2 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L162) | **KEEP & OPTIMIZE (High Impact)** |
| `_score_network` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L77), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L77), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L106), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L106) | **KEEP & OPTIMIZE (High Impact)** |
| `_walk` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L205), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L205), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L262), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L292) | **KEEP & OPTIMIZE (High Impact)** |
| `classify_allocation` | v1 | [sieve_deterministic.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve_deterministic.py#L67), [sieve_deterministic.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve_deterministic.py#L67), [sieve_deterministic.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve_deterministic.py#L67), [sieve_deterministic.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve_deterministic.py#L67) | **KEEP & OPTIMIZE (High Impact)** |
| `eval_cond` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L459) | **KEEP & OPTIMIZE (High Impact)** |
| `eval_rule` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L485) | **KEEP & OPTIMIZE (High Impact)** |
| `evaluate` | v1 | [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/baseline_engine.py#L13), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.3/baseline_engine.py#L13), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.4/baseline_engine.py#L13), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.5/baseline_engine.py#L13) | **KEEP & OPTIMIZE (High Impact)** |
| `get_os_mode` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L14), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L14) | **KEEP & OPTIMIZE (High Impact)** |
| `load_threats` | v1 | [core.py](file:////root/home/projects/project-lobster/src/core.py#L42) | **KEEP & OPTIMIZE (High Impact)** |
| `scan` | v1 | [iron_dome.py](file:////root/home/projects/project-lobster/src/iron_dome.py#L71) | **KEEP & OPTIMIZE (High Impact)** |
| `scan_allowlist` | v1 | [iron_dome.py](file:////root/home/projects/project-lobster/src/iron_dome.py#L88) | **KEEP & OPTIMIZE (High Impact)** |
| `score_pid_table` | v1 | [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/sieve.py#L275), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.3/sieve.py#L275), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.4/sieve.py#L332), [sieve.py](file:////root/home/projects/project-mantis/agent_v0.5.5/sieve.py#L362) | **KEEP & OPTIMIZE (High Impact)** |

### 📦 Data Parsing & General Utilities (17 skills)

| Skill Name | Current Version | Source File | Action / Recommendation |
| :--- | :--- | :--- | :--- |
| `_coalesce_ranges` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L336), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L336), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L366), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L366) | **KEEP (Low Priority for Evolution)** |
| `_load_json_cache` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L294), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L294), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L302), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L302) | **KEEP (Low Priority for Evolution)** |
| `_run_memmap_meta` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L304), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L304), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L312), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L312) | **KEEP (Low Priority for Evolution)** |
| `_transient_watcher` | v1 | [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.5/live_collector.py#L487) | **KEEP (Low Priority for Evolution)** |
| `collect_network_connections` | v1 | [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.3/live_collector.py#L155), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.4/live_collector.py#L155), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.5/live_collector.py#L155) | **KEEP (Low Priority for Evolution)** |
| `convert_to_gemini_schema` | v1 | [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L139) | **KEEP (Low Priority for Evolution)** |
| `find_user_in_tree` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L97), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L97), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L97), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L97) | **KEEP (Low Priority for Evolution)** |
| `generate_hexdump` | v2 | [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.3/live_collector.py#L120), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.4/live_collector.py#L120), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.5/live_collector.py#L120) | **KEEP (Low Priority for Evolution)** |
| `get_evidence_context` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L63), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L63), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L63), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L63) | **KEEP (Low Priority for Evolution)** |
| `parse_ip_port` | v2 | [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.3/live_collector.py#L134), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.4/live_collector.py#L134), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.5/live_collector.py#L134) | **KEEP (Low Priority for Evolution)** |
| `resolve_refs` | v1 | [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L142) | **KEEP (Low Priority for Evolution)** |
| `resolve_username_from_pid` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L73), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L73), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L73), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L73) | **KEEP (Low Priority for Evolution)** |
| `sanitize_evidence` | v1 | [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/agent.py#L309), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.3/agent.py#L309), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.4/agent.py#L309), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L407) | **KEEP (Low Priority for Evolution)** |
| `sanitize_results` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L627), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L710), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L710), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L826) | **KEEP (Low Priority for Evolution)** |
| `uppercase_types` | v1 | [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L160) | **KEEP (Low Priority for Evolution)** |
| `validate_path` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L13), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L13), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L13), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L13) | **KEEP (Low Priority for Evolution)** |
| `verify_report` | v1 | [mock_playbook_test.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mock_playbook_test.py#L125) | **KEEP (Low Priority for Evolution)** |

### 📦 Framework Infrastructure (22 skills)

| Skill Name | Current Version | Source File | Action / Recommendation |
| :--- | :--- | :--- | :--- |
| `__init__` | v1 | [orchestrator.py](file:////root/home/projects/project-hermit/v0.0.9/orchestrator.py#L35), [sandbox.py](file:////root/home/projects/project-hermit/v0.0.9/sandbox.py#L16), [hermit_daemon.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_daemon.py#L24), [dashboard.py](file:////root/home/projects/project-lobster/dashboard.py#L48), [core.py](file:////root/home/projects/project-lobster/src/core.py#L57), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/agent.py#L88), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/agent.py#L126), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/agent.py#L132), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/agent.py#L144), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/baseline_engine.py#L7), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L289), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.3/agent.py#L88), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.3/agent.py#L126), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.3/agent.py#L132), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.3/agent.py#L144), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.3/baseline_engine.py#L7), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L289), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L289), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.4/baseline_engine.py#L7), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.4/agent.py#L88), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.4/agent.py#L126), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.4/agent.py#L132), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.4/agent.py#L144), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L88), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L126), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L132), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L176), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L242), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L248), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L259), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L289), [baseline_engine.py](file:////root/home/projects/project-mantis/agent_v0.5.5/baseline_engine.py#L7) | **AVOID/EXCLUDE** |
| `_get_playbook_path` | v1 | [config.py](file:////root/home/projects/project-mantis/agent_v0.5.5/config.py#L12) | **AVOID/EXCLUDE** |
| `check_and_apply_context_decay` | v1 | [hermit_daemon.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_daemon.py#L70) | **AVOID/EXCLUDE** |
| `check_rec` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L218), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L218), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L218), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L218) | **AVOID/EXCLUDE** |
| `check_status` | v1 | [hermit_chat.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_chat.py#L27) | **AVOID/EXCLUDE** |
| `compile_report` | v1 | [monitor_evolution.py](file:////root/home/projects/project-hermit/v0.0.9/monitor_evolution.py#L9) | **AVOID/EXCLUDE** |
| `generate_adversarial_tests` | v1 | [orchestrator.py](file:////root/home/projects/project-hermit/v0.0.9/orchestrator.py#L349) | **AVOID/EXCLUDE** |
| `get_historical_adversarial_tests` | v1 | [orchestrator.py](file:////root/home/projects/project-hermit/v0.0.9/orchestrator.py#L340) | **AVOID/EXCLUDE** |
| `get_state_hash` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L305), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L305), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L305) | **AVOID/EXCLUDE** |
| `hex_search` | v74 | [orchestrator.py](file:////root/home/projects/project-hermit/v0.0.9/orchestrator.py#L886) | **AVOID/EXCLUDE** |
| `inject_task` | v1 | [hermit_chat.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_chat.py#L154) | **AVOID/EXCLUDE** |
| `list_branches` | v1 | [hermit_chat.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_chat.py#L54) | **AVOID/EXCLUDE** |
| `list_skills` | v1 | [hermit_chat.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_chat.py#L38) | **AVOID/EXCLUDE** |
| `monitor` | v1 | [monitor_evolution.py](file:////root/home/projects/project-hermit/v0.0.9/monitor_evolution.py#L74) | **AVOID/EXCLUDE** |
| `obfuscate_telemetry` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L21), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L21), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L21), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L21) | **AVOID/EXCLUDE** |
| `run_analytical_chat` | v1 | [hermit_chat.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_chat.py#L106) | **AVOID/EXCLUDE** |
| `run_with_timer` | v1 | [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/mcp_server.py#L39), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.3/mcp_server.py#L39), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.4/mcp_server.py#L39), [mcp_server.py](file:////root/home/projects/project-mantis/agent_v0.5.5/mcp_server.py#L39) | **AVOID/EXCLUDE** |
| `safe_api_call` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L57), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L57), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L57), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L57) | **AVOID/EXCLUDE** |
| `safe_write_cache` | v1 | [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.3/live_collector.py#L378), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.4/live_collector.py#L378), [live_collector.py](file:////root/home/projects/project-mantis/agent_v0.5.5/live_collector.py#L403) | **AVOID/EXCLUDE** |
| `send_message` | v1 | [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/agent.py#L95), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.3/agent.py#L95), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.4/agent.py#L95), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L95), [agent.py](file:////root/home/projects/project-mantis/agent_v0.5.5/agent.py#L184) | **AVOID/EXCLUDE** |
| `show_failures` | v1 | [hermit_chat.py](file:////root/home/projects/project-hermit/v0.0.9/hermit_chat.py#L85) | **AVOID/EXCLUDE** |
| `verify_and_trigger_cache` | v1 | [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.2_stable-hackathon/orchestrator.py#L664), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.3/orchestrator.py#L754), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.4/orchestrator.py#L754), [orchestrator.py](file:////root/home/projects/project-mantis/agent_v0.5.5/orchestrator.py#L870) | **AVOID/EXCLUDE** |


---

## 🚫 Avoid & Exclude Framework Infrastructure (Core Recommendations)

> [!WARNING]
> We must explicitly exclude **Framework Infrastructure** skills from Project Hermit's optimization loop. Letting the autonomous Discovery Agent mutate these files is highly risky.

### Why We Must Avoid Optimizing Framework Infrastructure:
1. **Self-Referential Loop Crash:** Skills like `__init__`, `check_status`, `list_skills`, and `show_failures` represent the active running code of `project-hermit` itself. If the background daemon mutates them, it updates the files we are currently executing, which can crash the daemon or lock the SQLite database.
2. **Subprocess/API Failures:** Functions like `safe_api_call`, `send_message`, and `run_with_timer` wrap external calls. Mutating them in the sandbox can lead to false validation failures (or worse, unwanted parallel API calls that consume tokens/quota).
3. **No ROI (Return on Investment):** CLI commands like `list_branches` or `show_failures` only execute on-demand when a developer runs them. Optimizing their latency from 5ms to 1ms saves nothing, yet costs hundreds of API tokens to evolve.

### Target Focus for v0.0.9:
Instead, we should direct the evolutionary loop towards:
* **Deep memory extraction:** `carve_memory_strings`, `carve_and_stream_strings` (processing gigabytes of RAM dumps).
* **Regex timelines:** `search_disk_timeline`, `verify_report` (matching strings in massive bodyfiles).
* **Deterministic filtering:** `score_pid_table`, `_score_network` (sorting and evaluating telemetry).

---

## 🛠️ Step-by-Step Instructions to Apply Exclusions in v0.0.9

To enforce these exclusions, we will configure the Discovery Agent inside [orchestrator.py](file:///root/home/projects/project-hermit/v0.0.9/orchestrator.py) to skip any functions that match the "Framework Infrastructure" criteria or belong to the framework-level files.

This can be done by extending the hardcoded skip tuple in [orchestrator.py:L461](file:///root/home/projects/project-hermit/v0.0.9/orchestrator.py#L461):
```python
if node.name in ("main", "run_loop", "setUp", "tearDown", "test_self_patching", "check_status", "list_skills", "list_branches", "show_failures", "monitor", "compile_report", "safe_api_call", "send_message", "run_analytical_chat"):
    continue
```
And restricting search directories to avoid scanning `self_dir` for self-introspection.
