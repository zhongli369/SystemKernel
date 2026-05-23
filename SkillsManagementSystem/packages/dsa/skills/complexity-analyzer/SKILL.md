---
name: complexity-analyzer
description: Deep analysis of algorithm time and space complexity. Derive Big-O bounds with mathematical reasoning, analyze best/average/worst cases, and explain amortized complexity. Use when the user asks about algorithm performance, complexity, or efficiency.
argument-hint: [code-or-algorithm-description]
---

# Complexity Analyzer

Analyze time and space complexity of algorithms with rigorous but accessible explanations. Provide practical guidance on real-world performance, not just theoretical bounds.

## Input

- `$0` — Code snippet, algorithm description, or solution reference
- `$1` — Optional: specific analysis focus (time/space/amortized/all)

## References

- Common complexity reference: `~/.claude/skills/complexity-analyzer/references/complexity-reference.md`

## Workflow

### Step 1: Identify Basic Operations
1. What is the dominant operation? (comparisons, swaps, arithmetic, memory access)
2. What is the input size parameter n?
3. Are there multiple input size parameters? (e.g., n nodes + m edges in graph)

### Step 2: Analyze Time Complexity

**For iterative code:**
- Count loop iterations and their nested relationships
- Identify early-exit conditions
- Handle non-trivial loop bounds (e.g., inner loop depends on outer)

**For recursive code:**
- Write recurrence relation: T(n) = a·T(n/b) + f(n)
- Apply Master Theorem or recursion tree method
- For non-standard recurrences, use substitution method

**For complex data structures:**
- Account for underlying operations (hash table O(1) avg, BST O(log n), etc.)

### Step 3: Analyze Space Complexity
1. **Input space**: Is it counted? (usually yes for online algos, no for in-place)
2. **Auxiliary space**: Extra arrays, hash maps, etc.
3. **Recursion stack**: Max depth × frame size
4. **Output space**: Usually not counted

### Step 4: Case Analysis

| Case | Scenario | Example |
|------|----------|---------|
| Best | Most favorable input | Sorted array for insertion sort: O(n) |
| Average | Expected over all inputs | Random array for quicksort: O(n log n) |
| Worst | Most adversarial input | Reverse-sorted for quicksort: O(n²) |

### Step 5: Provide Chinese Explanation
用中文通俗解释：
- **为什么**这个复杂度是这样的？（直观理解）
- **什么时候**会退化到最坏情况？（实际影响）
- **能不能**进一步优化？（改进方向）

## Output Format

```
## 复杂度分析

### 时间复杂度
- 最坏: O(n²) — 当输入完全逆序时，每次 partition 只减少1个元素
- 平均: O(n log n) — partition 平均将数组分成两半
- 最好: O(n log n) — 每次 partition 恰好平分

### 空间复杂度
- 辅助空间: O(log n) — 递归调用栈深度
- 原地操作，不需要额外数组

### 推导过程
外层循环 n 次，内层循环...
T(n) = n + (n-1) + (n-2) + ... + 1 = n(n+1)/2 = O(n²)

### 优化建议
使用随机 pivot 可以避免最坏情况...
```

## Rules

- Always state units clearly: operations (comparisons, swaps), memory (bytes/elements)
- For logarithmic complexity, specify the base (log₂ for divide-by-2, ln for continuous)
- If using amortized analysis, explain the accounting or potential method
- When O(1) operations have large constants (e.g., 1000×), mention it
- For NP-hard problems, state the known complexity class
- Compare against known lower bounds when relevant
- Explain the "常数因子" (constant factor) when it matters in practice

## Common Complexity Reference

| Complexity | n=10 | n=100 | n=10³ | n=10⁶ | n=10⁹ | Typical Algorithm |
|-----------|------|-------|-------|-------|-------|-------------------|
| O(1) | 1 | 1 | 1 | 1 | 1 | Direct access |
| O(log n) | 3 | 7 | 10 | 20 | 30 | Binary search |
| O(√n) | 3 | 10 | 32 | 1000 | 31623 | Prime check (naive) |
| O(n) | 10 | 100 | 10³ | 10⁶ | 10⁹ | Linear scan |
| O(n log n) | 30 | 700 | 10⁴ | 2×10⁷ | 3×10¹⁰ | Sort, heap ops |
| O(n²) | 100 | 10⁴ | 10⁶ | 10¹² | 10¹⁸ | Nested loops |
| O(n³) | 10³ | 10⁶ | 10⁹ | 10¹⁸ | 10²⁷ | Floyd-Warshall |
| O(2ⁿ) | 1024 | 10³⁰ | — | — | — | Brute-force subsets |
| O(n!) | 3.6×10⁶ | 10¹⁵⁸ | — | — | — | Permutations |

### Feasibility Guide (1 second ≈ 10⁸ operations)
- O(n) for n ≤ 10⁸
- O(n log n) for n ≤ 10⁷
- O(n²) for n ≤ 10⁴
- O(n³) for n ≤ 500
- O(2ⁿ) for n ≤ 25
- O(n!) for n ≤ 10

## Related Skills
- [dsa-problem-solver](../dsa-problem-solver/) — Main problem solving
- [code-tracer](../code-tracer/) — Step-by-step execution
- [algorithm-explainer](../algorithm-explainer/) — Pseudocode and diagrams
- [reflective-reasoning](../../base/skills/reflective-reasoning/) — Formal proofs
