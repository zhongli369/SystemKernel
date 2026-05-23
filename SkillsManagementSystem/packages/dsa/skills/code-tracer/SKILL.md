---
name: code-tracer
description: Step-by-step code execution tracing with variable state visualization. Trace algorithm execution line-by-line, showing variable changes, call stack, and data structure state at each step. Use when debugging, understanding algorithm flow, or demonstrating code execution.
argument-hint: [code-file-and-input]
---

# Code Tracer

Trace algorithm execution step by step, visualizing variable state changes and data structure evolution. Ideal for debugging and teaching algorithm behavior.

## Input

- `$0` — Code file path or code snippet
- `$1` — Input data / test case to trace
- `$2` — Optional: language (cpp/java/python, auto-detect if omitted)

## References

- Tracing templates: `~/.claude/skills/code-tracer/references/trace-templates.md`

## Workflow

### Step 1: Parse the Code
1. Identify the target function/method
2. Extract all variables and their initial values
3. Map out the control flow: loops, conditionals, recursion
4. Identify key data structures (arrays, maps, trees, etc.)

### Step 2: Execute with Input
Simulate the code line-by-line with the given input:

For each significant step, record:
- **Line number** currently executing
- **Variables** and their current values
- **Data structures** state (array contents, tree shape, etc.)
- **Loop counters** and iteration progress
- **Recursion depth** and call stack (if applicable)

### Step 3: Output the Trace

Use ASCII art for visual representation:

```
=== Code Trace: binarySearch(nums=[2,5,8,12,16], target=8) ===

Step 1 | Line 3: left=0, right=4
        nums: [2, 5, 8, 12, 16]
               ^           ^
             left        right

Step 2 | Line 4: mid = 0 + (4-0)/2 = 2
        nums: [2, 5, 8, 12, 16]
                     ^
                    mid

Step 3 | Line 5: nums[2]=8 == target=8 → return 2 ✓
```

For trees:
```
    5
   / \
  3   8
 / \   \
1   4   9

DFS order: 5 → 3 → 1 → 4 → 8 → 9
BFS order: 5 → 3 → 8 → 1 → 4 → 9
```

For DP tables:
```
dp table for LCS("abc", "ac"):
    "" a  c
""  0  0  0
a   0  1  1
b   0  1  1
c   0  1  2  ← answer
```

### Step 4: Summarize
- Total steps executed
- Final return value
- Memory usage pattern
- Any edge cases encountered

## Rules

- Keep each step concise — show only what changed
- Use `...` to skip repetitive iterations (show first 2-3, then skip, show last 1-2)
- For large arrays: show only relevant portion with context
- Highlight the "aha moment" — the key step where the algorithm logic clicks
- Use Chinese for explanations when the user's problem is in Chinese
- For recursive functions, use indentation to show call depth
- Flag infinite loops, excessive recursion, or performance issues in the trace

## Trace Formats by Data Structure

### Array
```
index:  0   1   2   3   4
value: [2,  5,  8,  12, 16]
         ^               ^
        L=0             R=4
```

### Linked List
```
1 → 2 → 3 → 4 → 5 → null
s       f
(slow)  (fast)
```

### Stack
```
| 3 | ← top
| 2 |
| 1 | ← bottom
```

### Queue
```
front → [1, 2, 3] ← back
```

### Graph (Adjacency List)
```
0 → [1, 2]
1 → [0, 3]
2 → [0, 3]
3 → [1, 2]

BFS from 0:
visited: {0}  queue: [1, 2]  level: 1
```

## Related Skills
- [dsa-problem-solver](../dsa-problem-solver/) — Main problem solving
- [complexity-analyzer](../complexity-analyzer/) — Complexity analysis
- [debugger](../../base/skills/debugger/) — Systematic debugging
