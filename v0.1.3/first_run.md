[ PROJECT HERMIT - Orchestrator Baseline ]

--- Starting Evolution Cycle for Skill: hex_search (Current Version: 1) ---
Running baseline implementation in sandbox...
Baseline performance: Duration = 531.33 ms, Max RSS = 22356 KB
Querying Gemini API for optimized mutation...

Gemini Optimization Rationale:
The original `hex_search` implementation uses a naive O(N*M) algorithm, which is highly inefficient for large inputs, as evidenced by the 531.33 ms execution time for the given test case. To optimize for speed, the most straightforward and Pythonic approach is to leverage the built-in `bytes.find()` method. This method is implemented in C and uses highly optimized search algorithms (like Boyer-Moore or similar) internally, making it significantly faster than a pure Python loop. The strategy is to repeatedly call `data_bytes.find(pattern, start_index)` in a loop, updating `start_index` to `found_index + 1` after each match to find subsequent occurrences. This approach drastically reduces the number of comparisons and leverages the underlying C implementation for maximum performance. Memory usage will also be minimal, as it only stores the list of indices.
Testing mutation in sandbox...
Mutation performance: Duration = 275.75 ms, Max RSS = 3328 KB
INTEGRATION SUCCESS: Mutation is faster by 255.57 ms!
Skill 'hex_search' successfully updated (Version 2).
