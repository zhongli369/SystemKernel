# Language-Specific Coding Standards for DSA

## C++ Standards

### Containers
```cpp
vector<int> nums;           // dynamic array
unordered_map<int, int> mp; // hash map (O(1) avg)
map<int, int> mp;           // ordered map (O(log n))
unordered_set<int> st;      // hash set
stack<int> stk;             // stack
queue<int> q;               // queue
deque<int> dq;              // double-ended queue
priority_queue<int> pq;     // max-heap (default)
priority_queue<int, vector<int>, greater<int>> min_pq; // min-heap
```

### Common Operations
```cpp
sort(nums.begin(), nums.end());                    // ascending
sort(nums.begin(), nums.end(), greater<int>());    // descending
auto it = lower_bound(nums.begin(), nums.end(), x); // first >= x
auto it = upper_bound(nums.begin(), nums.end(), x); // first > x
reverse(nums.begin(), nums.end());
int mx = *max_element(nums.begin(), nums.end());
```

### String
```cpp
string s = "hello";
s.substr(start, len);     // substring
s.find("ll");             // first index or string::npos
s += '!';                 // append
to_string(42);            // int to string
stoi("42");               // string to int
```

## Java Standards

### Containers
```java
List<Integer> list = new ArrayList<>();
Map<Integer, Integer> map = new HashMap<>();
Set<Integer> set = new HashSet<>();
Stack<Integer> stack = new Stack<>();
Queue<Integer> queue = new LinkedList<>();
Deque<Integer> deque = new ArrayDeque<>();
PriorityQueue<Integer> minHeap = new PriorityQueue<>();
PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
```

### Common Operations
```java
Collections.sort(list);
Collections.sort(list, Collections.reverseOrder());
int idx = Collections.binarySearch(list, x); // returns -(insertion point)-1 if not found
Collections.reverse(list);
int mx = Collections.max(list);
```

### String
```java
String s = "hello";
s.substring(start, end);  // [start, end)
s.indexOf("ll");
s += '!';                  // use StringBuilder for loops
String.valueOf(42);        // int to string
Integer.parseInt("42");    // string to int
```

### Array Utilities
```java
int[] arr = new int[n];
Arrays.sort(arr);
int idx = Arrays.binarySearch(arr, x);
Arrays.fill(arr, 0);
int[] copy = Arrays.copyOf(arr, n);
```

## Python Standards

### Containers
```python
nums: list[int] = []
mp: dict[int, int] = {}
st: set[int] = set()
from collections import deque, defaultdict, Counter
dq: deque[int] = deque()
cnt: Counter = Counter()
d: defaultdict[int, list] = defaultdict(list)
import heapq
heap: list[int] = []
heapq.heappush(heap, x)   # min-heap
heapq.heappop(heap)
# Max-heap: push -x, pop -x
```

### Common Operations
```python
nums.sort()                     # in-place
nums.sort(reverse=True)
sorted_nums = sorted(nums)      # new list
from bisect import bisect_left, bisect_right
idx = bisect_left(nums, x)      # first >= x
idx = bisect_right(nums, x)     # first > x
nums.reverse()
mx = max(nums)
```

### String
```python
s = "hello"
s[start:end]       # slice
s.find("ll")       # -1 if not found
s += "!"           # join for loops
str(42)            # int to string
int("42")          # string to int
```

### Useful Builtins
```python
all(iterable)      # True if all truthy
any(iterable)      # True if any truthy
enumerate(iterable) # (index, value) pairs
zip(a, b)          # parallel iteration
from itertools import accumulate, combinations, permutations
```
