---
name: dsa-problem-solver
description: Solve data structures & algorithms problems with clean C++/Java/Python implementations, Chinese explanations, complexity analysis, and multiple solution approaches. Use when the user asks to solve algorithm problems, LeetCode-style questions, or needs DSA help with code.
argument-hint: [problem-description-or-url]
---

# DSA Problem Solver

Solve algorithm and data structure problems with clean, readable code and thorough analysis. All explanations in Chinese. Code in C++, Java, or Python.

## Input

- `$0` — Problem description, LeetCode URL, or problem number
- `$1` — Optional: preferred language (cpp/java/python, default: user's choice)

## References

- Solution templates and patterns: `~/.claude/skills/dsa-problem-solver/references/solution-patterns.md`
- Language-specific style guides: `~/.claude/skills/dsa-problem-solver/references/lang-guides.md`

## Workflow

### Step 1: Problem Analysis (题意分析)
1. Parse the problem statement — identify input format, output format, constraints
2. Extract key information: data size N, time/space limits, edge cases
3. Classify the problem type: array, string, tree, graph, DP, greedy, search, etc.
4. **中文解释题意** — 用通俗易懂的中文重新描述问题，确保理解准确

### Step 2: Solution Design (算法设计)
1. Brainstorm 2-3 viable approaches (brute force → optimized → optimal)
2. For each approach, sketch:
   - Core idea (核心思路)
   - Algorithm steps (算法步骤)
   - Time complexity
   - Space complexity
   - Pros and cons
3. Select the primary solution (usually the optimal one) for detailed implementation

### Step 3: Complexity Analysis (复杂度分析)
- **时间复杂度**: Derive step by step, state best/average/worst case
- **空间复杂度**: Account for input storage, auxiliary structures, recursion stack
- For amortized analysis (e.g., dynamic array, union-find), explain the amortized bound

### Step 4: Implementation (代码实现)
Write clean, well-structured code following language conventions:

**Code style rules:**
- Use meaningful variable names (no single-letter except loop indices i, j, k)
- No unnecessary abstractions — keep it simple and direct
- Handle edge cases explicitly
- No comments explaining WHAT the code does — only WHY for non-obvious logic
- Follow standard library patterns for each language

**C++:**
- Prefer `vector` over raw arrays, `string` over `char*`
- Use STL containers and algorithms
- RAII and references, avoid raw pointers
- `const` correctness where appropriate

**Java:**
- Standard class structure with public method
- Use ArrayList, HashMap, etc. over arrays when dynamic
- Follow Java naming conventions (camelCase)

**Python:**
- Use type hints for clarity
- List comprehensions over explicit loops where readable
- Leverage built-in functions and standard library

### Step 5: Solution Comparison (解法对比)
Present a comparison table:

| 解法 | 时间复杂度 | 空间复杂度 | 适用场景 | 代码复杂度 |
|------|-----------|-----------|---------|-----------|
| 暴力法 | O(n²) | O(1) | 小数据量 | 简单 |
| 优化法 | O(n log n) | O(n) | 中等数据 | 中等 |
| 最优解 | O(n) | O(1) | 大数据量 | 较难 |

Explain which solution to choose in interviews vs. production.

### Step 6: Testing (测试验证)
1. Provide test cases: normal case, edge case (empty, single, max constraint), corner case
2. Walk through the code with a small example step by step
3. Verify output against expected

## Rules

- Always start with problem understanding in Chinese
- Provide at least 2 solution approaches for non-trivial problems
- Default to the most practical solution, not necessarily the asymptotically optimal one
- Code must be runnable as-is (include imports, class definitions)
- Explain complexity in plain Chinese, not just Big-O notation
- When the problem is a classic LeetCode problem, reference the problem number
- Keep implementation under 50 lines when possible — prefer clarity over cleverness

## Problem Type Quick Reference

| Type | Key Techniques | Common Pitfalls |
|------|---------------|-----------------|
| Array/ String | Two pointers, sliding window, prefix sum | Index bounds, empty input |
| Linked List | Dummy head, fast/slow pointer | Null checks, cycle detection |
| Tree | DFS, BFS, recursion, iteration | Base case, stack overflow |
| Graph | BFS, DFS, Union-Find, Topo sort | Visited tracking, disconnected components |
| DP | Memoization, tabulation, state transition | State definition, base cases, space optimization |
| Greedy | Sorting, heap, proof of correctness | Local vs global optimum |
| Binary Search | Search space, condition function | Off-by-one, infinite loop |
| Backtracking | Pruning, state restoration | Duplicate results, recursion depth |
| Stack/Queue | Monotonic stack, deque | Empty check, order preservation |

## Related Skills
- [code-tracer](../code-tracer/) — Step-by-step execution tracing
- [complexity-analyzer](../complexity-analyzer/) — Deep complexity analysis
- [algorithm-explainer](../algorithm-explainer/) — Pseudocode and visual diagrams
- [debugger](../../base/skills/debugger/) — Systematic error debugging
- [code-review](../../base/skills/code-review/) — Code quality review
