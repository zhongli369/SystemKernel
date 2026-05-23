# Solution Patterns Reference

Common algorithmic patterns and when to apply them.

## Two Pointers
- **When**: Sorted array, palindrome, pair sum, partition
- **Pattern**: Left/right pointers moving inward, or fast/slow pointers
- **Complexity**: Usually O(n) time, O(1) space
- **Keywords**: "sorted", "in-place", "pair", "subarray sum"

## Sliding Window
- **When**: Substring/subarray with constraint, longest/shortest
- **Pattern**: Expand right, shrink left when condition violated
- **Complexity**: O(n) time, O(k) space for window state
- **Keywords**: "substring", "subarray", "contiguous", "at most K"

## Prefix Sum
- **When**: Range sum queries, subarray sum equals K
- **Pattern**: pre[i] = sum(nums[0..i-1]), sum(L,R) = pre[R+1] - pre[L]
- **Complexity**: O(n) build, O(1) query
- **Keywords**: "sum of subarray", "range sum"

## Fast & Slow Pointers
- **When**: Cycle detection, middle of linked list, happy number
- **Pattern**: Fast moves 2 steps, slow moves 1 step
- **Complexity**: O(n) time, O(1) space
- **Keywords**: "cycle", "loop", "middle"

## Monotonic Stack
- **When**: Next greater/smaller element, largest rectangle, temperature
- **Pattern**: Maintain increasing/decreasing stack, pop when condition broken
- **Complexity**: O(n) time (each element pushed/popped once)
- **Keywords**: "next greater", "next smaller", "largest rectangle"

## Binary Search
- **When**: Sorted array, search space monotonic, minimize maximum
- **Pattern**: while (left < right) { mid = left + (right-left)/2; if (condition) left = mid+1 else right = mid; }
- **Complexity**: O(log n) time
- **Keywords**: "sorted", "minimum possible maximum", "K operations"

## BFS
- **When**: Shortest path (unweighted), level-order, minimum steps
- **Pattern**: Queue + visited set, process level by level
- **Complexity**: O(V+E) time, O(V) space
- **Keywords**: "shortest", "minimum steps", "level", "grid"

## DFS / Backtracking
- **When**: All combinations/permutations, tree path sum, maze
- **Pattern**: Recursion + state restoration (backtrack), or explicit stack
- **Complexity**: Exponential in worst case
- **Keywords**: "all possible", "combinations", "permutations", "paths"

## Dynamic Programming
- **When**: Optimal substructure, overlapping subproblems
- **Pattern**: Define dp[i] state, transition equation, base case, iteration order
- **Complexity**: Depends on state space × transitions
- **Keywords**: "maximum", "minimum", "number of ways", "longest"

### DP Sub-patterns
- **0/1 Knapsack**: dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt[i]] + val[i])
- **Unbounded Knapsack**: dp[i] = max(dp[i], dp[i-coin] + 1) for each coin
- **LCS**: dp[i][j] = dp[i-1][j-1]+1 or max(dp[i-1][j], dp[i][j-1])
- **LIS**: dp[i] = max(dp[j] + 1) for j < i and nums[j] < nums[i]
- **Edit Distance**: dp[i][j] = min of insert/delete/replace
- **Matrix Chain**: dp[i][j] = min(dp[i][k] + dp[k+1][j] + cost)

## Union-Find (DSU)
- **When**: Connected components, cycle detection in undirected graph
- **Pattern**: find() with path compression, union() by rank/size
- **Complexity**: O(α(n)) amortized per operation
- **Keywords**: "connected", "merge", "disjoint", "component"

## Topological Sort
- **When**: Dependency ordering, course schedule, build order
- **Pattern**: Kahn's algo (BFS + indegree) or DFS post-order
- **Complexity**: O(V+E) time
- **Keywords**: "prerequisite", "dependency", "order"

## Trie (Prefix Tree)
- **When**: Prefix matching, autocomplete, word search in dictionary
- **Pattern**: Node with children[26] + isEnd flag
- **Complexity**: O(L) per insert/search, L = word length
- **Keywords**: "prefix", "dictionary", "autocomplete", "word search"

## Greedy
- **When**: Local optimal = global optimal, interval scheduling
- **Pattern**: Sort by key attribute, then iterate making optimal local choice
- **Complexity**: Usually O(n log n) for sorting + O(n) scan
- **Keywords**: "minimum number of", "maximum number of non-overlapping"
