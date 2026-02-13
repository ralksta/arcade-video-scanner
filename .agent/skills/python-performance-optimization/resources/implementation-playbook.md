# Python Performance Optimization — Implementation Playbook

Detailed patterns, examples, and techniques for profiling and optimizing Python code.

---

## 1. CPU Profiling with cProfile

### Quick Profile a Script

```bash
python -m cProfile -s cumulative my_script.py
```

### Profile a Specific Function

```python
import cProfile
import pstats

def profile(func):
    """Decorator to profile a function."""
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats("cumulative")
        stats.print_stats(20)  # top 20 calls
        return result
    return wrapper
```

### Save & Analyze Profile Data

```python
import cProfile
import pstats

cProfile.run("main()", "output.prof")

# Analyze
stats = pstats.Stats("output.prof")
stats.sort_stats("cumulative")
stats.print_stats(30)
```

### Visualize with snakeviz

```bash
pip install snakeviz
python -m cProfile -o output.prof my_script.py
snakeviz output.prof
```

---

## 2. Line-Level Profiling

### line_profiler

```bash
pip install line_profiler
```

```python
# Decorate the target function
@profile
def slow_function():
    ...
```

```bash
kernprof -l -v my_script.py
```

---

## 3. Memory Profiling

### memory_profiler

```bash
pip install memory_profiler
```

```python
from memory_profiler import profile

@profile
def memory_heavy():
    data = [i ** 2 for i in range(10_000_000)]
    return sum(data)
```

```bash
python -m memory_profiler my_script.py
```

### tracemalloc (stdlib)

```python
import tracemalloc

tracemalloc.start()

# ... code under test ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

for stat in top_stats[:10]:
    print(stat)
```

### objgraph (reference leaks)

```bash
pip install objgraph
```

```python
import objgraph

objgraph.show_most_common_types(limit=10)
objgraph.show_growth(limit=10)
```

---

## 4. Common Optimization Patterns

### 4.1 Algorithmic Complexity

| Pattern | Before | After |
|---|---|---|
| Nested loops for lookups | O(n²) | O(n) with dict/set |
| Repeated list membership | `if x in list` | `if x in set` |
| Sorting for min/max | `sorted(lst)[0]` | `min(lst)` |

```python
# Before — O(n²)
for item in items:
    if item in large_list:
        process(item)

# After — O(n)
large_set = set(large_list)
for item in items:
    if item in large_set:
        process(item)
```

### 4.2 Generator Expressions

```python
# Before — builds full list in memory
total = sum([x ** 2 for x in range(10_000_000)])

# After — lazy evaluation, constant memory
total = sum(x ** 2 for x in range(10_000_000))
```

### 4.3 String Concatenation

```python
# Before — O(n²) due to immutable strings
result = ""
for s in strings:
    result += s

# After — O(n)
result = "".join(strings)
```

### 4.4 Caching / Memoization

```python
from functools import lru_cache

@lru_cache(maxsize=256)
def expensive_computation(n):
    # ...
    return result
```

### 4.5 Batch I/O

```python
# Before — one write per iteration
for row in rows:
    file.write(format(row))

# After — single write
file.write("".join(format(row) for row in rows))
```

### 4.6 Avoiding Repeated Attribute Lookups

```python
# Before
for item in items:
    obj.method(item)

# After — local reference
method = obj.method
for item in items:
    method(item)
```

---

## 5. Data Structure Selection

| Use Case | Recommended |
|---|---|
| Fast membership test | `set` or `frozenset` |
| Key → value mapping | `dict` |
| Ordered unique items | `dict.fromkeys()` |
| Queue (FIFO) | `collections.deque` |
| Counter / tallying | `collections.Counter` |
| Named records | `dataclasses.dataclass` or `namedtuple` |
| Large numeric arrays | `numpy.ndarray` |

---

## 6. Concurrency & Parallelism

### I/O-bound → `asyncio` or `threading`

```python
import asyncio

async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        return await asyncio.gather(*tasks)
```

### CPU-bound → `multiprocessing` or `concurrent.futures`

```python
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor() as executor:
    results = list(executor.map(cpu_heavy_fn, data_chunks))
```

---

## 7. Database & SQL Optimization

- **Use indexes** on frequently queried columns.
- **Batch inserts** with `executemany()` or bulk operations.
- **Avoid N+1 queries** — use JOINs or eager loading.
- **Use `EXPLAIN ANALYZE`** to understand query plans.
- **Connection pooling** to avoid connection overhead.

```python
# Batch insert
cursor.executemany(
    "INSERT INTO items (name, value) VALUES (?, ?)",
    [(item.name, item.value) for item in items]
)
```

---

## 8. File & I/O Optimization

- Read files in chunks instead of loading entirely into memory.
- Use `mmap` for large file random access.
- Buffer writes and flush periodically.

```python
import mmap

with open("large_file.bin", "r+b") as f:
    mm = mmap.mmap(f.fileno(), 0)
    # random access without loading entire file
    chunk = mm[1000:2000]
    mm.close()
```

---

## 9. Verification Checklist

After applying optimizations, verify:

- [ ] **Correctness** — all tests still pass
- [ ] **Benchmarks** — measure before/after with `timeit` or profiling
- [ ] **Memory** — check peak memory usage hasn't increased
- [ ] **Scalability** — test with realistic data sizes
- [ ] **Readability** — optimized code is still maintainable

```python
import timeit

# Quick benchmark
time = timeit.timeit("my_function()", globals=globals(), number=1000)
print(f"Average: {time / 1000:.6f}s per call")
```

---

## 10. Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad |
|---|---|
| Premature optimization | Wastes time, harms readability |
| Optimizing without profiling | You're guessing, not measuring |
| Global variables for speed | Marginal gain, significant maintenance cost |
| Micro-optimizations over algorithm fixes | 10x from algorithm > 1.1x from micro-opt |
| Ignoring GIL for CPU-bound threading | Threads won't parallelize CPU work |
