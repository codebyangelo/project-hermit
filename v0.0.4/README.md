# Project Hermit v0.0.4 - Multi-Objective Genetic Branching

Version `v0.0.4` implements a multi-candidate genetic branching architecture, shifting the evolution pipeline from sequential optimization to Pareto-optimal selection.

## Core Features
1. **Synthesizer Agent Variant Proposing:**
   * Instead of generating a single patch, the Synthesizer proposes three distinct optimization variants (e.g. slicing, regex, memoryviews, or built-in string methods).

2. **Parallel Evaluation:**
   * Evaluates all three variants inside isolated sandbox environments concurrently.

3. **Pareto Frontier Selection:**
   * Computes a multi-objective score factoring in **Latency** (1.0 weight), **Memory Max RSS** (0.1 weight), and **Code Complexity** (0.05 weight).
   * Ranks variants against the baseline and merges the branch that achieves the best overall Pareto-efficiency.

4. **Evolution Monitor Tool (`monitor_evolution.py`):**
   * Command-line tool to track active version mutations, count branches, verify logs, and compile markdown summary reports.
