# Project Hermit v0.0.5 - Telemetry Logging & Free-Tier Pacing Guards

Version `v0.0.5` implements telemetry constraints and protective limit guards to prevent API quota exhaustion (e.g. 429 rate limit errors on the Gemini Free Tier).

## Core Features
1. **Telemetry Logging (`limit_telemetry` table):**
   * Stores timestamps, latency, response sizes, error codes, and estimates prompt/completion tokens (TPM/RPD).

2. **RPM/TPM/RPD Rolling Calculation:**
   * Programmatically computes rolling metrics (Request Per Minute, Tokens Per Minute, Requests Per Day) from database records before submitting any LLM requests.

3. **Active Pacing & Throttle Cooldowns:**
   * Enforces a strict 5.0-second delay between consecutive calls to guarantee staying under the 15 RPM model ceiling.
   * Forces the background daemon to enter a 60-second cooldown sleep if rolling RPM exceeds 12 or rolling TPM exceeds 200,000.
