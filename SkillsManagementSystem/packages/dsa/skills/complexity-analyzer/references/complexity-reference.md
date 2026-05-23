# Complexity Analysis Reference

## Master Theorem

For recurrences of the form T(n) = a·T(n/b) + f(n):

| Case | Condition | Result |
|------|-----------|--------|
| 1 | f(n) = O(n^{log_b a - ε}) | T(n) = Θ(n^{log_b a}) |
| 2 | f(n) = Θ(n^{log_b a}) | T(n) = Θ(n^{log_b a} · log n) |
| 3 | f(n) = Ω(n^{log_b a + ε}) + regularity | T(n) = Θ(f(n)) |

### Examples
- Binary search: T(n) = T(n/2) + O(1) → Θ(log n) [Case 2]
- Merge sort: T(n) = 2T(n/2) + O(n) → Θ(n log n) [Case 2]
- Strassen: T(n) = 7T(n/2) + O(n²) → Θ(n^{log₂ 7}) ≈ O(n^2.81) [Case 1]

## Amortized Analysis

### Aggregate Method
Sum total cost of n operations, divide by n.

**Dynamic array expansion:** n insertions cost O(n) total → O(1) amortized per insertion.

### Accounting Method
Charge extra for cheap operations, use credit for expensive ones.

**Stack with multipop:** Push charges 2 (1 for push, 1 credit). Pop uses 1 credit. Amortized O(1).

### Potential Method
Φ(D_i) = potential of data structure after i operations.
Amortized cost = actual cost + ΔΦ.

## Common Data Structure Complexities

| Data Structure | Access | Search | Insert | Delete | Space |
|---------------|--------|--------|--------|--------|-------|
| Array | O(1) | O(n) | O(n) | O(n) | O(n) |
| Linked List | O(n) | O(n) | O(1) | O(1) | O(n) |
| Skip List | O(log n) | O(log n) | O(log n) | O(log n) | O(n log n) |
| Hash Table | — | O(1) | O(1) | O(1) | O(n) |
| BST (unbalanced) | O(n) | O(n) | O(n) | O(n) | O(n) |
| AVL / Red-Black | O(log n) | O(log n) | O(log n) | O(log n) | O(n) |
| Binary Heap | O(1) max | O(n) | O(log n) | O(log n) | O(n) |
| Fibonacci Heap | O(1) | — | O(1) | O(log n) | O(n) |

## Common Sorting Complexities

| Algorithm | Best | Average | Worst | Space | Stable |
|-----------|------|---------|-------|-------|--------|
| Bubble | O(n) | O(n²) | O(n²) | O(1) | Yes |
| Selection | O(n²) | O(n²) | O(n²) | O(1) | No |
| Insertion | O(n) | O(n²) | O(n²) | O(1) | Yes |
| Merge | O(n log n) | O(n log n) | O(n log n) | O(n) | Yes |
| Quick | O(n log n) | O(n log n) | O(n²) | O(log n) | No |
| Heap | O(n log n) | O(n log n) | O(n log n) | O(1) | No |
| Counting | O(n+k) | O(n+k) | O(n+k) | O(k) | Yes |
| Radix | O(nk) | O(nk) | O(nk) | O(n+k) | Yes |

## Common Graph Algorithm Complexities

| Algorithm | Time | Space |
|-----------|------|-------|
| BFS | O(V+E) | O(V) |
| DFS | O(V+E) | O(V) |
| Dijkstra (binary heap) | O((V+E) log V) | O(V) |
| Bellman-Ford | O(VE) | O(V) |
| Floyd-Warshall | O(V³) | O(V²) |
| Kruskal (MST) | O(E log E) | O(V) |
| Prim (binary heap) | O((V+E) log V) | O(V) |
| Topological Sort | O(V+E) | O(V) |
| Tarjan SCC | O(V+E) | O(V) |

## Space Complexity Notes

- **In-place**: O(1) auxiliary space (may modify input)
- **Recursion**: Don't forget the call stack
- **Tail recursion**: Can be O(1) stack with optimization
- **Memoization**: Trade time for space
- **Streaming**: O(1) by processing input incrementally
