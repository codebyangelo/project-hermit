# Project Hermit v0.0.6 - Return Annotation Regex & Context Decay

Version `v0.0.6` optimizes the code parser regex to support standard type hints and implements database log pruning using automated context summary decay.

## Core Features
1. **Return Annotation Safe Regex:**
   * Uses an updated regex parser `rf"def\s+{skill_name}...` that accounts for python function return type annotations (such as `-> list:`), preventing the synthesizer from outputting overlapping function declarations.

2. **Context Summary Decay:**
   * If a skill variant encounters consecutive test crashes (> 3 failures in `reality_tests` table), Project Hermit triggers context decay.
   * Calls a summarizer assistant to condense the compile/run-time tracebacks into a concise 2-sentence summary.
   * Appends the summary directly to the skill's description and purges the old detailed failure logs from the database, preventing DB size bloat.
