"""Coding duel tasks: real multi-file work done by an agent with tools (list_files, read_file, write_file, run).

Each task: id, kind, prompt, files (the project the agent starts with, incl. a small visible test it may run),
hidden (grading tests the agent never sees: test_* functions, each one point) and ref (a reference solution, only used
by `run_duel.py --check` to prove the hidden tests are right).
Hidden tests can call run_cli([...]) to run a program in the project folder the way a user would.
"""

TASKS = []


def task(id, kind, prompt, files, hidden, ref):
    TASKS.append({"id": id, "kind": kind, "prompt": prompt, "files": files, "hidden": hidden, "ref": ref})


# ============================================================================ 1. LRU cache with TTL
task("lru_ttl", "build",
     "Create cache.py with a class LRUCache(capacity, ttl=None, clock=time.monotonic). Methods: get(key, default=None), "
     "put(key, value), delete(key) -> bool, __len__, __contains__, keys() -> list from least to most recently used. "
     "get and put make a key the most recently used. When a put would exceed capacity, evict the least recently used key. "
     "If ttl (seconds) is set, an entry older than ttl since its last put is expired: get returns default, it is not "
     "counted by len/contains/keys, and expired entries are evicted before live ones. capacity < 1 raises ValueError. "
     "Use the clock function for all time reads. A visible test is in test_cache.py.",
     {"test_cache.py": "from cache import LRUCache\nc = LRUCache(2)\nc.put('a', 1); c.put('b', 2); c.get('a'); c.put('c', 3)\n"
                       "assert 'b' not in c and c.get('a') == 1 and len(c) == 2\nprint('ok')\n"},
     """
from cache import LRUCache

class Clock:
    def __init__(self): self.t = 100.0
    def __call__(self): return self.t

def test_basic_eviction():
    c = LRUCache(2); c.put('a', 1); c.put('b', 2); c.put('c', 3)
    assert 'a' not in c and c.get('b') == 2 and c.get('c') == 3

def test_get_refreshes():
    c = LRUCache(2); c.put('a', 1); c.put('b', 2); c.get('a'); c.put('c', 3)
    assert c.keys() == ['a', 'c']

def test_put_existing_updates_and_refreshes():
    c = LRUCache(2); c.put('a', 1); c.put('b', 2); c.put('a', 10); c.put('c', 3)
    assert c.get('a') == 10 and 'b' not in c and len(c) == 2

def test_default_and_delete():
    c = LRUCache(3); c.put('x', None)
    assert c.get('x', 5) is None and c.get('nope', 7) == 7
    assert c.delete('x') is True and c.delete('x') is False and len(c) == 0

def test_capacity_validation():
    for bad in (0, -1):
        try:
            LRUCache(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('no ValueError')

def test_ttl_expiry():
    clk = Clock(); c = LRUCache(3, ttl=10, clock=clk)
    c.put('a', 1); clk.t += 5; c.put('b', 2); clk.t += 6
    assert c.get('a') is None and 'a' not in c and c.get('b') == 2 and len(c) == 1 and c.keys() == ['b']

def test_ttl_get_does_not_extend():
    clk = Clock(); c = LRUCache(3, ttl=10, clock=clk)
    c.put('a', 1); clk.t += 9; assert c.get('a') == 1; clk.t += 2
    assert c.get('a', 'gone') == 'gone'

def test_expired_evicted_before_live():
    clk = Clock(); c = LRUCache(2, ttl=10, clock=clk)
    c.put('old', 1); clk.t += 1; c.put('live', 2); c.get('old')   # old is most recently used
    clk.t += 9.5                                               # old expired (10.5), live not (9.5)
    c.put('new', 3)
    assert c.get('live') == 2 and c.get('new') == 3 and 'old' not in c

def test_keys_order_many():
    c = LRUCache(5)
    for i in range(8):
        c.put(i, i)
    c.get(4); c.put(9, 9)
    assert c.keys() == [5, 6, 7, 4, 9]
""",
     {"cache.py": """import time
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity, ttl=None, clock=time.monotonic):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self._d = OrderedDict()   # key -> (value, put_time)

    def _expired(self, t, now):
        return self.ttl is not None and now - t > self.ttl

    def _purge(self):
        now = self.clock()
        for k in [k for k, (_, t) in self._d.items() if self._expired(t, now)]:
            del self._d[k]

    def get(self, key, default=None):
        self._purge()
        if key not in self._d:
            return default
        self._d.move_to_end(key)
        return self._d[key][0]

    def put(self, key, value):
        self._purge()
        if key in self._d:
            del self._d[key]
        elif len(self._d) >= self.capacity:
            self._d.popitem(last=False)
        self._d[key] = (value, self.clock())

    def delete(self, key):
        self._purge()
        return self._d.pop(key, None) is not None or False

    def __len__(self):
        self._purge()
        return len(self._d)

    def __contains__(self, key):
        self._purge()
        return key in self._d

    def keys(self):
        self._purge()
        return list(self._d)
"""})
# delete of a key holding None must still return True: fix the reference
TASKS[-1]["ref"]["cache.py"] = TASKS[-1]["ref"]["cache.py"].replace(
    "        return self._d.pop(key, None) is not None or False\n",
    "        if key in self._d:\n            del self._d[key]\n            return True\n        return False\n")

# ============================================================================ 2. expression evaluator
task("calc", "build",
     "Create calc.py with evaluate(expr: str) -> float. Support numbers (ints and decimals like 2.5 or .5), + - * /, "
     "^ for power (right-associative, binds tighter than unary minus: -2^2 = -4), parentheses, unary minus and plus, "
     "and spaces anywhere. Normal precedence: ^ > unary -/+ > * / > + -. Raise ValueError for any invalid expression "
     "(empty, unbalanced parentheses, unknown characters, two numbers in a row, trailing operator) and ZeroDivisionError "
     "for division by zero. Do NOT use eval, exec, compile or the ast module. A visible test is in test_calc.py.",
     {"test_calc.py": "from calc import evaluate\nassert evaluate('1 + 2 * 3') == 7\nassert evaluate('(1+2)*3') == 9\nprint('ok')\n"},
     """
from calc import evaluate
import calc, inspect, re

def raises(expr, exc=ValueError):
    try:
        evaluate(expr)
    except exc:
        return True
    except Exception:
        return False
    return False

def test_precedence():
    assert evaluate('2+3*4-5') == 9 and evaluate('10/4') == 2.5 and evaluate('8-3-2') == 3 and evaluate('16/4/2') == 2

def test_power_right_assoc():
    assert evaluate('2^3^2') == 512 and evaluate('(2^3)^2') == 64

def test_unary():
    assert evaluate('-3+5') == 2 and evaluate('-(2+3)') == -5 and evaluate('--4') == 4 and evaluate('+4*-2') == -8

def test_unary_vs_power():
    assert evaluate('-2^2') == -4 and evaluate('(-2)^2') == 4 and evaluate('2^-1') == 0.5

def test_decimals_spaces():
    assert abs(evaluate(' 1.5 *  .5 ') - 0.75) < 1e-12 and evaluate('3.0') == 3

def test_nested():
    assert evaluate('((1+2)*(3+4))/(7-0)') == 3 and evaluate('2*(3+(4-1)*2)') == 18

def test_invalid():
    assert all(raises(e) for e in ['', '   ', '(1+2', '1+2)', '1+', '* 3', '2 3', '1 + a', '()', '1..2', '4 ^'])

def test_div_zero():
    assert raises('1/0', ZeroDivisionError) and raises('5/(2-2)', ZeroDivisionError)

def test_no_eval():
    src = inspect.getsource(calc)
    assert not re.search(r'(?<![\\w.])(eval|exec|compile)\\s*\\(', src) and not re.search(r'^\\s*(import|from)\\s+ast\\b', src, re.M)
""",
     {"calc.py": """import re

_TOK = re.compile(r"\\s*(?:(\\d+\\.\\d*|\\.\\d+|\\d+)|(.))")


def _tokens(s):
    out = []
    pos = 0
    s = s.rstrip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            break
        num, op = m.groups()
        if num is not None:
            out.append(("n", float(num)))
        elif op in "+-*/^()":
            out.append(("o", op))
        else:
            raise ValueError(f"bad character {op!r}")
        pos = m.end()
    return out


class _P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expr(self):
        v = self.term()
        while self.peek() in (("o", "+"), ("o", "-")):
            op = self.take()[1]
            r = self.term()
            v = v + r if op == "+" else v - r
        return v

    def term(self):
        v = self.unary()
        while self.peek() in (("o", "*"), ("o", "/")):
            op = self.take()[1]
            r = self.unary()
            if op == "/":
                if r == 0:
                    raise ZeroDivisionError("division by zero")
                v = v / r
            else:
                v = v * r
        return v

    def unary(self):
        if self.peek() in (("o", "-"), ("o", "+")):
            op = self.take()[1]
            v = self.unary()
            return -v if op == "-" else v
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() == ("o", "^"):
            self.take()
            return base ** self.unary()
        return base

    def atom(self):
        kind, v = self.take()
        if kind == "n":
            return v
        if (kind, v) == ("o", "("):
            r = self.expr()
            if self.take() != ("o", ")"):
                raise ValueError("missing )")
            return r
        raise ValueError("unexpected token")


def evaluate(expr: str) -> float:
    toks = _tokens(expr)
    if not toks:
        raise ValueError("empty")
    p = _P(toks)
    v = p.expr()
    if p.i != len(toks):
        raise ValueError("trailing input")
    return float(v)
"""})

# ============================================================================ 3. key-value store with transactions
task("kvstore", "build",
     "Create kv.py with a class KV: set(key, value), get(key) -> value or None, delete(key), count(value) -> number of "
     "keys currently holding value, begin(), commit(), rollback(). Transactions can be nested: rollback undoes only the "
     "innermost open transaction; commit applies ALL open transactions permanently. rollback or commit with no open "
     "transaction raises RuntimeError('no transaction'). count must be correct inside transactions too. "
     "Visible test: test_kv.py.",
     {"test_kv.py": "from kv import KV\ns = KV(); s.set('a', 10); s.begin(); s.set('a', 20); s.rollback()\nassert s.get('a') == 10\nprint('ok')\n"},
     """
from kv import KV

def test_basic():
    s = KV(); s.set('a', 1); s.set('b', 1)
    assert s.get('a') == 1 and s.count(1) == 2 and s.get('zz') is None
    s.delete('a'); assert s.get('a') is None and s.count(1) == 1

def test_rollback():
    s = KV(); s.set('a', 10); s.begin(); s.set('a', 20); s.set('b', 5); s.delete('a')
    assert s.get('a') is None and s.count(5) == 1
    s.rollback(); assert s.get('a') == 10 and s.get('b') is None and s.count(5) == 0

def test_nested_rollback_inner_only():
    s = KV(); s.begin(); s.set('a', 1); s.begin(); s.set('a', 2); s.rollback()
    assert s.get('a') == 1; s.rollback(); assert s.get('a') is None

def test_commit_all():
    s = KV(); s.begin(); s.set('a', 1); s.begin(); s.set('b', 2); s.commit()
    assert s.get('a') == 1 and s.get('b') == 2
    try:
        s.rollback()
    except RuntimeError:
        pass
    else:
        raise AssertionError('rollback after commit should fail')

def test_no_transaction_errors():
    s = KV()
    for f in (s.rollback, s.commit):
        try:
            f()
        except RuntimeError as e:
            assert 'no transaction' in str(e)
        else:
            raise AssertionError('missing RuntimeError')

def test_count_in_nested():
    s = KV(); s.set('a', 7); s.set('b', 7); s.begin(); s.set('a', 8); s.begin(); s.set('c', 7)
    assert s.count(7) == 2 and s.count(8) == 1
    s.rollback(); assert s.count(7) == 1; s.rollback(); assert s.count(7) == 2 and s.count(8) == 0

def test_delete_then_set_in_tx():
    s = KV(); s.set('k', 'v'); s.begin(); s.delete('k'); s.set('k', 'w'); s.begin(); s.delete('k'); s.rollback()
    assert s.get('k') == 'w'; s.rollback(); assert s.get('k') == 'v'

def test_many_values_fast():
    s = KV()
    for i in range(20000):
        s.set(i, i % 3)
    s.begin()
    for i in range(0, 20000, 2):
        s.set(i, 5)
    for _ in range(2000):
        s.count(5)
    s.rollback(); assert s.count(5) == 0 and s.count(0) == 6667
""",
     {"kv.py": """from collections import Counter

_MISSING = object()


class KV:
    def __init__(self):
        self.data, self.counts, self.undo = {}, Counter(), []

    def _write(self, key, value):
        old = self.data.get(key, _MISSING)
        if self.undo and key not in self.undo[-1]:
            self.undo[-1][key] = old
        if old is not _MISSING:
            self.counts[old] -= 1
        if value is _MISSING:
            self.data.pop(key, None)
        else:
            self.data[key] = value
            self.counts[value] += 1

    def set(self, key, value):
        self._write(key, value)

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        if key in self.data:
            self._write(key, _MISSING)

    def count(self, value):
        return self.counts[value]

    def begin(self):
        self.undo.append({})

    def rollback(self):
        if not self.undo:
            raise RuntimeError("no transaction")
        changes = self.undo.pop()
        saved, self.undo = self.undo, []
        for k, old in changes.items():
            self._write(k, old)
        self.undo = saved

    def commit(self):
        if not self.undo:
            raise RuntimeError("no transaction")
        self.undo = []
"""})

# ============================================================================ 4. free time slots
task("schedule", "build",
     "Create schedule.py with free_slots(busy, day_start='09:00', day_end='17:00', min_minutes=30). busy is a list of "
     "(start, end) 'HH:MM' strings, unsorted, possibly overlapping or touching, and possibly partly outside the day. "
     "Return the free intervals inside [day_start, day_end] as a list of 'HH:MM-HH:MM' strings in time order, keeping "
     "only those at least min_minutes long. An interval with end <= start raises ValueError. Visible test: test_schedule.py.",
     {"test_schedule.py": "from schedule import free_slots\nassert free_slots([('10:00', '11:00')]) == ['09:00-10:00', '11:00-17:00']\nprint('ok')\n"},
     """
from schedule import free_slots

def test_simple():
    assert free_slots([('10:00', '11:00')]) == ['09:00-10:00', '11:00-17:00']

def test_overlap_and_unsorted():
    assert free_slots([('13:00', '14:00'), ('09:30', '10:30'), ('10:00', '11:00')]) == ['09:00-09:30', '11:00-13:00', '14:00-17:00']

def test_touching_merge():
    assert free_slots([('10:00', '11:00'), ('11:00', '12:00')], min_minutes=1) == ['09:00-10:00', '12:00-17:00']

def test_min_minutes_filter():
    assert free_slots([('09:20', '12:00'), ('12:25', '16:40')]) == []
    assert free_slots([('09:20', '12:00'), ('12:25', '16:40')], min_minutes=20) == ['09:00-09:20', '12:00-12:25', '16:40-17:00']

def test_outside_day():
    assert free_slots([('07:00', '09:45'), ('16:30', '19:00')]) == ['09:45-16:30']
    assert free_slots([('06:00', '08:00'), ('18:00', '19:00')]) == ['09:00-17:00']

def test_whole_day_busy():
    assert free_slots([('08:00', '18:00')]) == []

def test_custom_day():
    assert free_slots([], day_start='08:30', day_end='10:00', min_minutes=90) == ['08:30-10:00']
    assert free_slots([], day_start='08:30', day_end='10:00', min_minutes=91) == []

def test_invalid():
    for bad in ([('11:00', '10:00')], [('10:00', '10:00')]):
        try:
            free_slots(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('no ValueError')
""",
     {"schedule.py": """def _m(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _s(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def free_slots(busy, day_start="09:00", day_end="17:00", min_minutes=30):
    ivs = []
    for a, b in busy:
        a, b = _m(a), _m(b)
        if b <= a:
            raise ValueError("end must be after start")
        ivs.append((a, b))
    ivs.sort()
    ds, de = _m(day_start), _m(day_end)
    out, cur = [], ds
    for a, b in ivs:
        if b <= cur:
            continue
        if a > cur:
            end = min(a, de)
            if end - cur >= min_minutes:
                out.append(f"{_s(cur)}-{_s(end)}")
        cur = max(cur, b)
        if cur >= de:
            break
    if de - cur >= min_minutes:
        out.append(f"{_s(cur)}-{_s(de)}")
    return out
"""})

# ============================================================================ 5. shortest path
task("routes", "build",
     "Create routes.py with shortest_path(edges, src, dst). edges is a list of (a, b, weight) for UNDIRECTED roads with "
     "non-negative weights (several roads between the same towns are possible). Return (total_cost, [src, ..., dst]) of a "
     "cheapest route, or None when dst cannot be reached. src == dst returns (0, [src]) even if src has no roads. "
     "A negative weight raises ValueError. Must handle 50,000 edges in well under a second. Visible test: test_routes.py.",
     {"test_routes.py": "from routes import shortest_path\nassert shortest_path([('A','B',1),('B','C',2),('A','C',5)], 'A', 'C') == (3, ['A','B','C'])\nprint('ok')\n"},
     """
from routes import shortest_path
import random, time

def valid(edges, res, src, dst):
    cost, path = res
    if path[0] != src or path[-1] != dst:
        return False
    best = {}
    for a, b, w in edges:
        for x, y in ((a, b), (b, a)):
            best[(x, y)] = min(best.get((x, y), float('inf')), w)
    total = 0
    for x, y in zip(path, path[1:]):
        if (x, y) not in best:
            return False
        total += best[(x, y)]
    return abs(total - cost) < 1e-9

def test_basic():
    e = [('A', 'B', 1), ('B', 'C', 2), ('A', 'C', 5)]
    assert shortest_path(e, 'A', 'C') == (3, ['A', 'B', 'C'])

def test_undirected():
    e = [('A', 'B', 1), ('B', 'C', 2)]
    assert shortest_path(e, 'C', 'A') == (3, ['C', 'B', 'A'])

def test_parallel_edges():
    e = [('A', 'B', 9), ('A', 'B', 2), ('B', 'C', 1)]
    r = shortest_path(e, 'A', 'C'); assert r[0] == 3 and valid(e, r, 'A', 'C')

def test_unreachable_and_unknown():
    e = [('A', 'B', 1), ('C', 'D', 1)]
    assert shortest_path(e, 'A', 'D') is None and shortest_path(e, 'A', 'Z') is None

def test_same_node():
    assert shortest_path([], 'X', 'X') == (0, ['X'])

def test_zero_weights():
    e = [('A', 'B', 0), ('B', 'C', 0), ('A', 'C', 1)]
    r = shortest_path(e, 'A', 'C'); assert r[0] == 0 and valid(e, r, 'A', 'C')

def test_negative():
    try:
        shortest_path([('A', 'B', -1)], 'A', 'B')
    except ValueError:
        pass
    else:
        raise AssertionError('no ValueError')

def test_large_random():
    rnd = random.Random(7)
    n = 10000
    e = [(i, i + 1, 10) for i in range(n - 1)] + [(rnd.randrange(n), rnd.randrange(n), rnd.randint(1, 100)) for _ in range(40000)]
    t = time.time(); r = shortest_path(e, 0, n - 1); dt = time.time() - t
    assert r is not None and valid(e, r, 0, n - 1) and dt < 3.0
    # check optimality against a simple reference Dijkstra
    import heapq
    adj = {}
    for a, b, w in e:
        adj.setdefault(a, []).append((b, w)); adj.setdefault(b, []).append((a, w))
    dist = {0: 0}; pq = [(0, 0)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist.get(v, float('inf')):
                dist[v] = d + w; heapq.heappush(pq, (d + w, v))
    assert r[0] == dist[n - 1]
""",
     {"routes.py": """import heapq


def shortest_path(edges, src, dst):
    adj = {}
    for a, b, w in edges:
        if w < 0:
            raise ValueError("negative weight")
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))
    if src == dst:
        return (0, [src])
    if src not in adj or dst not in adj:
        return None
    dist, prev, pq = {src: 0}, {}, [(0, 0, src)]
    n = 0
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == dst:
            path = [u]
            while path[-1] != src:
                path.append(prev[path[-1]])
            return (d, path[::-1])
        for v, w in adj[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v], prev[v] = nd, u
                n += 1
                heapq.heappush(pq, (nd, n, v))
    return None
"""})

# ============================================================================ 6. token bucket
task("ratelimit", "build",
     "Create ratelimit.py with class TokenBucket(rate, capacity, clock=time.monotonic): tokens refill continuously at "
     "rate tokens per second up to capacity; the bucket starts full. allow(n=1) -> bool takes n tokens if available, else "
     "takes nothing and returns False. wait_time(n=1) -> float seconds until n tokens would be available (0 if now). "
     "n > capacity raises ValueError in both methods; rate <= 0 or capacity <= 0 raises ValueError. Use only the clock "
     "function for time. Also add class KeyedLimiter(rate, capacity, clock=time.monotonic) with allow(key, n=1) keeping "
     "one bucket per key. Visible test: test_ratelimit.py.",
     {"test_ratelimit.py": "from ratelimit import TokenBucket\nb = TokenBucket(1, 2, clock=lambda: 0.0)\nassert b.allow() and b.allow() and not b.allow()\nprint('ok')\n"},
     """
from ratelimit import TokenBucket, KeyedLimiter

class Clock:
    def __init__(self): self.t = 50.0
    def __call__(self): return self.t

def test_starts_full():
    c = Clock(); b = TokenBucket(1, 3, clock=c)
    assert b.allow() and b.allow() and b.allow() and not b.allow()

def test_refill():
    c = Clock(); b = TokenBucket(2, 4, clock=c)
    assert b.allow(4) and not b.allow(); c.t += 1.0
    assert b.allow(2) and not b.allow()

def test_cap():
    c = Clock(); b = TokenBucket(10, 3, clock=c); b.allow(3); c.t += 100
    assert b.allow(3) and not b.allow()

def test_fail_takes_nothing():
    c = Clock(); b = TokenBucket(1, 5, clock=c); b.allow(3)
    assert not b.allow(3) and b.allow(2)

def test_wait_time():
    c = Clock(); b = TokenBucket(2, 4, clock=c)
    assert b.wait_time() == 0; b.allow(4)
    assert abs(b.wait_time(3) - 1.5) < 1e-9; c.t += 1.5
    assert abs(b.wait_time(3)) < 1e-9 and b.allow(3)

def test_fractional_refill():
    c = Clock(); b = TokenBucket(0.5, 1, clock=c); b.allow(); c.t += 1.0
    assert not b.allow(); c.t += 1.0; assert b.allow()

def test_validation():
    c = Clock()
    for args in ((0, 1), (1, 0), (-1, 5)):
        try:
            TokenBucket(*args, clock=c)
        except ValueError:
            pass
        else:
            raise AssertionError('no ValueError')
    b = TokenBucket(1, 2, clock=c)
    for f in (b.allow, b.wait_time):
        try:
            f(3)
        except ValueError:
            pass
        else:
            raise AssertionError('no ValueError for n > capacity')

def test_keyed():
    c = Clock(); k = KeyedLimiter(1, 1, clock=c)
    assert k.allow('a') and not k.allow('a') and k.allow('b'); c.t += 1
    assert k.allow('a')
""",
     {"ratelimit.py": """import time


class TokenBucket:
    def __init__(self, rate, capacity, clock=time.monotonic):
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be > 0")
        self.rate, self.capacity, self.clock = rate, capacity, clock
        self.tokens, self.t = float(capacity), clock()

    def _refill(self):
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
        self.t = now

    def _check(self, n):
        if n > self.capacity:
            raise ValueError("n exceeds capacity")

    def allow(self, n=1):
        self._check(n)
        self._refill()
        if self.tokens + 1e-12 >= n:
            self.tokens -= n
            return True
        return False

    def wait_time(self, n=1):
        self._check(n)
        self._refill()
        return max(0.0, (n - self.tokens) / self.rate)


class KeyedLimiter:
    def __init__(self, rate, capacity, clock=time.monotonic):
        self.rate, self.capacity, self.clock, self.b = rate, capacity, clock, {}

    def allow(self, key, n=1):
        if key not in self.b:
            self.b[key] = TokenBucket(self.rate, self.capacity, self.clock)
        return self.b[key].allow(n)
"""})

# ============================================================================ 7. CSV report CLI
task("csv_report", "build",
     "Create report.py, a command line program: python report.py FILE --group COLUMN --sum COLUMN [--sort total|key] "
     "[--top N]. It reads a CSV file with a header, groups rows by the --group column and sums the --sum column. Rows "
     "whose sum value is empty or not a number are skipped and counted. Print JSON to stdout: {\"groups\": [{\"key\": k, "
     "\"total\": t, \"rows\": n}, ...], \"skipped\": s}. Totals are numbers (int when whole, else float rounded to 2 "
     "decimals). --sort key (default) sorts by key ascending; --sort total sorts by total descending, ties by key. --top N "
     "keeps the first N groups after sorting. A missing file or unknown column prints an error to stderr and exits with "
     "code 2. Also expose main(argv) -> int. sales.csv is an example input.",
     {"sales.csv": "region,amount,rep\nNorth,120,ann\nSouth,80.5,bob\nNorth,30,cy\nEast,,dan\nSouth,19.5,eve\nEast,45,fay\nWest,abc,gus\n"},
     """
import json, os

def run(args, cwd=None):
    r = run_cli(['report.py'] + args)
    return r.returncode, r.stdout, r.stderr

def write(name, text):
    with open(name, 'w', encoding='utf-8', newline='') as f:
        f.write(text)

def test_example_default():
    code, out, _ = run(['sales.csv', '--group', 'region', '--sum', 'amount'])
    d = json.loads(out)
    assert code == 0 and d['skipped'] == 2
    assert d['groups'] == [{'key': 'East', 'total': 45, 'rows': 1}, {'key': 'North', 'total': 150, 'rows': 2},
                           {'key': 'South', 'total': 100, 'rows': 2}]

def test_sort_total_top():
    write('t1.csv', 'k,v\\nb,5\\na,5\\nc,9\\nd,1\\n')
    d = json.loads(run(['t1.csv', '--group', 'k', '--sum', 'v', '--sort', 'total', '--top', '3'])[1])
    assert [g['key'] for g in d['groups']] == ['c', 'a', 'b']

def test_float_rounding():
    write('t2.csv', 'k,v\\nx,0.1\\nx,0.2\\ny,1.005\\ny,2\\n')
    d = json.loads(run(['t2.csv', '--group', 'k', '--sum', 'v'])[1])
    g = {x['key']: x['total'] for x in d['groups']}
    assert g['x'] == 0.3 and isinstance(g['x'], float) and abs(g['y'] - 3.0) < 0.011

def test_int_when_whole():
    write('t3.csv', 'k,v\\nx,1.5\\nx,2.5\\n')
    out = run(['t3.csv', '--group', 'k', '--sum', 'v'])[1]
    assert json.loads(out)['groups'][0]['total'] == 4 and '"total": 4,' in out.replace('4.0', 'X') or json.loads(out)['groups'][0]['total'] == 4 and type(json.loads(out)['groups'][0]['total']) is int

def test_missing_file():
    code, out, err = run(['nope.csv', '--group', 'k', '--sum', 'v'])
    assert code == 2 and err.strip()

def test_unknown_column():
    code, out, err = run(['sales.csv', '--group', 'zone', '--sum', 'amount'])
    assert code == 2 and err.strip()

def test_quoted_fields():
    write('t4.csv', 'name,amount\\n"Smith, J",10\\n"Smith, J",5\\nLee,1\\n')
    d = json.loads(run(['t4.csv', '--group', 'name', '--sum', 'amount'])[1])
    assert {'key': 'Smith, J', 'total': 15, 'rows': 2} in d['groups']

def test_main_function():
    import report
    assert report.main(['sales.csv', '--group', 'rep', '--sum', 'amount', '--top', '1']) == 0
""",
     {"report.py": """import argparse
import csv
import json
import sys


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--group", required=True)
    p.add_argument("--sum", required=True, dest="sumcol")
    p.add_argument("--sort", choices=["total", "key"], default="key")
    p.add_argument("--top", type=int)
    a = p.parse_args(argv)
    try:
        f = open(a.file, newline="", encoding="utf-8")
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    with f:
        r = csv.DictReader(f)
        if a.group not in (r.fieldnames or []) or a.sumcol not in (r.fieldnames or []):
            print("error: unknown column", file=sys.stderr)
            return 2
        groups, skipped = {}, 0
        for row in r:
            v = _num(row[a.sumcol])
            if v is None:
                skipped += 1
                continue
            g = groups.setdefault(row[a.group], [0.0, 0])
            g[0] += v
            g[1] += 1
    items = [{"key": k, "total": (int(round(t)) if abs(t - round(t)) < 1e-9 else round(t, 2)), "rows": n}
             for k, (t, n) in groups.items()]
    if a.sort == "key":
        items.sort(key=lambda g: g["key"])
    else:
        items.sort(key=lambda g: (-g["total"], g["key"]))
    if a.top is not None:
        items = items[:a.top]
    print(json.dumps({"groups": items, "skipped": skipped}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""})

# ============================================================================ 8. markdown table
task("mdtable", "build",
     "Create mdtable.py with to_markdown(rows, columns=None, align=None). rows is a list of dicts. columns defaults to "
     "the keys in first-seen order across all rows. Missing values are empty cells; None is an empty cell; other values "
     "use str(). Pad every column to its widest cell (header included, minimum width 3). align is a dict column -> "
     "'left'|'right'|'center' (default left) and sets both the padding and the separator row (:--- , ---:, :---:). "
     "The | character inside a cell must be escaped as \\\\|. Lines are '| a | b |' with one space around each cell, "
     "joined by newlines, no trailing newline. Visible test: test_mdtable.py.",
     {"test_mdtable.py": "from mdtable import to_markdown\nassert to_markdown([{'a': 1, 'b': 'x'}]) == '| a   | b   |\\n| --- | --- |\\n| 1   | x   |'\nprint('ok')\n"},
     """
from mdtable import to_markdown

def test_basic():
    assert to_markdown([{'a': 1, 'b': 'x'}]) == '| a   | b   |\\n| --- | --- |\\n| 1   | x   |'

def test_width():
    t = to_markdown([{'name': 'Alexander', 'n': 5}, {'name': 'Bo', 'n': 12345}])
    assert t.split('\\n') == ['| name      | n     |', '| --------- | ----- |', '| Alexander | 5     |', '| Bo        | 12345 |']

def test_columns_union_order_and_missing():
    t = to_markdown([{'a': 1}, {'b': 2, 'a': 3}, {'c': None}])
    assert t.split('\\n')[0] == '| a   | b   | c   |' and t.split('\\n')[2] == '| 1   |     |     |' and t.split('\\n')[4] == '|     |     |     |'

def test_explicit_columns():
    t = to_markdown([{'a': 1, 'b': 2}], columns=['b'])
    assert t == '| b   |\\n| --- |\\n| 2   |'

def test_align():
    t = to_markdown([{'x': 'ab', 'y': 'longer', 'z': 'c'}], align={'y': 'right', 'z': 'center'})
    lines = t.split('\\n')
    assert lines[1] == '| --- | -----: | :-: |' and lines[2] == '| ab  | longer |  c  |'
    t2 = to_markdown([{'num': 7}, {'num': 1234}], align={'num': 'right'})
    assert t2.split('\\n')[2] == '|    7 |' and t2.split('\\n')[1] == '| ---: |'

def test_center_odd():
    t = to_markdown([{'head': 'ab'}], align={'head': 'center'})
    lines = t.split('\\n')
    assert lines[1] == '| :--: |' and lines[2] in ('|  ab  |',)

def test_pipe_escape():
    t = to_markdown([{'c': 'a|b'}])
    assert t.split('\\n')[2] == '| a\\\\|b |'

def test_empty_rows():
    assert to_markdown([], columns=['q']) == '| q   |\\n| --- |'
""",
     {"mdtable.py": """def _cell(v):
    if v is None:
        return ""
    return str(v).replace("|", "\\\\|")


def _pad(s, w, a):
    if a == "right":
        return s.rjust(w)
    if a == "center":
        return s.center(w)
    return s.ljust(w)


def _sep(w, a):
    if a == "right":
        return "-" * (w - 1) + ":"
    if a == "center":
        return ":" + "-" * (w - 2) + ":"
    return "-" * w


def to_markdown(rows, columns=None, align=None):
    align = align or {}
    if columns is None:
        columns = []
        for r in rows:
            for k in r:
                if k not in columns:
                    columns.append(k)
    cells = [[_cell(r.get(c)) for c in columns] for r in rows]
    heads = [_cell(c) for c in columns]
    widths = [max([3, len(h)] + [len(row[i]) for row in cells]) for i, h in enumerate(heads)]
    al = [align.get(c, "left") for c in columns]
    line = lambda vals: "| " + " | ".join(_pad(v, w, a) for v, w, a in zip(vals, widths, al)) + " |"
    out = [line(heads), "| " + " | ".join(_sep(w, a) for w, a in zip(widths, al)) + " |"]
    out += [line(r) for r in cells]
    return "\\n".join(out)
"""})

# ============================================================================ 9. sudoku
task("sudoku", "build",
     "Create sudoku.py with solve(puzzle: str) -> str | None. puzzle is 81 characters, digits 1-9 and '.' or '0' for "
     "empty cells (whitespace and newlines anywhere must be ignored). Return the solved grid as 81 digits, or None if it "
     "has no solution or the given clues already conflict. Any other length or character raises ValueError. It must "
     "solve hard puzzles in under 2 seconds each. Also add is_valid_solution(grid: str) -> bool. Visible test: "
     "test_sudoku.py.",
     {"test_sudoku.py": "from sudoku import solve, is_valid_solution\n"
                        "p = '53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79'\n"
                        "s = solve(p)\nassert s and is_valid_solution(s) and s.startswith('534678912')\nprint('ok')\n"},
     """
from sudoku import solve, is_valid_solution
import time

HARD = ['8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..',
        '..53.....8......2..7..1.5..4....53...1..7...6..32...8..6.5....9..4....3......97..',
        '.....6....59.....82....8....45........3........6..3.54...325..6..................']

def consistent(p, s):
    p = p.replace('0', '.')
    return all(a == '.' or a == b for a, b in zip(p, s))

def test_easy():
    p = '53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79'
    s = solve(p); assert s == '534678912672195348198342567859761423426853791713924856961537284287419635345286179'

def test_hard_fast():
    for p in HARD[:2]:
        t = time.time(); s = solve(p)
        assert s and is_valid_solution(s) and consistent(p, s) and time.time() - t < 2.0

def test_zeros_and_whitespace():
    p = '53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79'.replace('.', '0')
    p = '\\n'.join(p[i:i + 9] for i in range(0, 81, 9))
    s = solve(p); assert s and s.startswith('534678912')

def test_conflicting_clues():
    p = '55' + '.' * 79
    assert solve(p) is None

def test_unsolvable():
    p = '12345678.' + '........9' + '.' * 63   # cell 9 needs 9 but column 9 has a 9 lower... row1 col9 cannot be 9 (col has 9)
    assert solve(p) is None

def test_bad_input():
    for bad in ('1' * 80, '1' * 82, 'x' + '.' * 80):
        try:
            solve(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('no ValueError')

def test_is_valid_solution():
    good = '534678912672195348198342567859761423426853791713924856961537284287419635345286179'
    assert is_valid_solution(good) and not is_valid_solution(good[:-2] + good[-1] + good[-2]) and not is_valid_solution('1' * 81)
""",
     {"sudoku.py": """def _parse(p):
    s = "".join(p.split())
    if len(s) != 81 or any(c not in "0123456789." for c in s):
        raise ValueError("bad puzzle")
    return [0 if c in ".0" else int(c) for c in s]


_UNITS = [[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)] + \\
         [[(br + r) * 9 + bc + c for r in range(3) for c in range(3)] for br in (0, 3, 6) for bc in (0, 3, 6)]
_PEERS = [sorted({p for u in _UNITS if i in u for p in u} - {i}) for i in range(81)]


def solve(puzzle):
    g = _parse(puzzle)
    for i, v in enumerate(g):
        if v and any(g[p] == v for p in _PEERS[i]):
            return None
    cand = [0] * 81

    def options(i):
        used = {g[p] for p in _PEERS[i]}
        return [d for d in range(1, 10) if d not in used]

    def bt():
        best, bopts = -1, None
        for i in range(81):
            if g[i] == 0:
                o = options(i)
                if not o:
                    return False
                if bopts is None or len(o) < len(bopts):
                    best, bopts = i, o
                    if len(o) == 1:
                        break
        if best < 0:
            return True
        for d in bopts:
            g[best] = d
            if bt():
                return True
        g[best] = 0
        return False

    return "".join(map(str, g)) if bt() else None


def is_valid_solution(grid):
    s = "".join(grid.split())
    if len(s) != 81 or not s.isdigit() or "0" in s:
        return False
    return all(len({s[i] for i in u}) == 9 for u in _UNITS)
"""})

# ============================================================================ 10. JSON schema-lite validator
task("schema", "build",
     "Create schema.py with validate(data, schema) -> list of error strings (empty list = valid). Support these schema "
     "keys: type ('object','array','string','integer','number','boolean','null'; integer excludes bool and floats, number "
     "accepts int and float but not bool), required (list), properties (dict of sub-schemas), additionalProperties "
     "(False forbids unknown keys), items (schema for every array element), enum, minimum, maximum, minLength, "
     "maxLength. Each error is 'PATH: message' where PATH is '$' for the root, '$.name' for a property and '$.list[2]' "
     "for an array index (e.g. '$.users[0].age: expected integer'). Collect ALL errors, not just the first. "
     "Visible test: test_schema.py.",
     {"test_schema.py": "from schema import validate\nassert validate({'a': 1}, {'type': 'object'}) == []\n"
                        "assert len(validate('x', {'type': 'integer'})) == 1\nprint('ok')\n"},
     """
from schema import validate

S = {'type': 'object', 'required': ['name', 'users'], 'additionalProperties': False,
     'properties': {'name': {'type': 'string', 'minLength': 2},
                    'users': {'type': 'array', 'items': {'type': 'object', 'required': ['age'],
                              'properties': {'age': {'type': 'integer', 'minimum': 0, 'maximum': 150},
                                             'role': {'enum': ['admin', 'user']}}}}}}

def paths(errs):
    return sorted(e.split(':')[0] for e in errs)

def test_valid():
    assert validate({'name': 'ok', 'users': [{'age': 3, 'role': 'user'}]}, S) == []

def test_types():
    assert validate(True, {'type': 'integer'}) and validate(1.5, {'type': 'integer'}) and not validate(2, {'type': 'number'})
    assert validate(True, {'type': 'number'}) and not validate(None, {'type': 'null'}) and validate([], {'type': 'object'})

def test_nested_paths():
    errs = validate({'name': 'ok', 'users': [{'age': 3}, {'age': 'x'}, {'age': 200, 'role': 'boss'}]}, S)
    assert paths(errs) == ['$.users[1].age', '$.users[2].age', '$.users[2].role']

def test_required_and_additional():
    errs = validate({'nam': 'x'}, S)
    p = paths(errs)
    assert p.count('$') >= 2 or ('$' in p and len(errs) >= 3)
    assert any('name' in e for e in errs) and any('users' in e for e in errs) and any('nam' in e for e in errs)

def test_all_errors_collected():
    errs = validate({'name': 'x', 'users': 'no', 'extra': 1}, S)
    assert len(errs) == 3

def test_string_length():
    assert validate('abc', {'type': 'string', 'minLength': 1, 'maxLength': 3}) == []
    assert len(validate('abcd', {'type': 'string', 'maxLength': 3})) == 1 and len(validate('', {'minLength': 1})) == 1

def test_min_max_number():
    assert validate(5, {'minimum': 5, 'maximum': 5}) == [] and len(validate(4.9, {'minimum': 5})) == 1

def test_root_path():
    e = validate(3, {'type': 'string'})
    assert len(e) == 1 and e[0].startswith('$:')

def test_type_error_stops_deeper_checks():
    e = validate({'name': 5, 'users': []}, S)
    assert paths(e) == ['$.name']
""",
     {"schema.py": """_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(data, schema, path="$"):
    errs = []
    t = schema.get("type")
    if t and not _TYPES[t](data):
        return [f"{path}: expected {t}"]
    if "enum" in schema and data not in schema["enum"]:
        errs.append(f"{path}: not one of {schema['enum']}")
    num = isinstance(data, (int, float)) and not isinstance(data, bool)
    if num and "minimum" in schema and data < schema["minimum"]:
        errs.append(f"{path}: below minimum {schema['minimum']}")
    if num and "maximum" in schema and data > schema["maximum"]:
        errs.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errs.append(f"{path}: longer than {schema['maxLength']}")
    if isinstance(data, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in data:
                errs.append(f"{path}: missing required property '{k}'")
        if schema.get("additionalProperties") is False:
            for k in data:
                if k not in props:
                    errs.append(f"{path}: unexpected property '{k}'")
        for k, sub in props.items():
            if k in data:
                errs += validate(data[k], sub, f"{path}.{k}")
    if isinstance(data, list) and "items" in schema:
        for i, v in enumerate(data):
            errs += validate(v, schema["items"], f"{path}[{i}]")
    return errs
"""})

# ============================================================================ 11. multi-file bug hunt
task("bugfix_inventory", "fix",
     "This inventory package has bugs. test_inventory.py fails. Find and fix ALL the bugs in the package so the "
     "behaviour matches the docstrings (the visible test does not cover everything). Do not change the tests or the "
     "public function names.",
     {"inventory/__init__.py": "from .store import Store\nfrom .pricing import line_total, order_total\n",
      "inventory/store.py": '''class Store:
    """In-memory stock. add(sku, qty) adds stock; remove(sku, qty) removes it and raises ValueError if there is not
    enough; tags(sku) returns the tags list of a sku (each sku has its OWN list); low_stock(limit) returns the skus
    with qty <= limit, sorted."""

    def __init__(self, items={}):
        self.items = items
        self._tags = {}

    def add(self, sku, qty, tags=[]):
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.items[sku] = self.items.get(sku, 0) + qty
        self._tags.setdefault(sku, tags).extend([])
        return self.items[sku]

    def tag(self, sku, tag):
        self._tags.setdefault(sku, []).append(tag)

    def tags(self, sku):
        return self._tags.get(sku, [])

    def remove(self, sku, qty):
        have = self.items.get(sku, 0)
        if qty > have + 1:
            raise ValueError("not enough stock")
        self.items[sku] = have - qty
        return self.items[sku]

    def low_stock(self, limit):
        return sorted(s for s, q in self.items.items() if q < limit)
''',
      "inventory/pricing.py": '''def line_total(price, qty, discount_pct=0):
    """price * qty minus a percentage discount, rounded to 2 decimals (half up, so 0.125 -> 0.13)."""
    total = price * qty * (1 - discount_pct / 100)
    return round(total, 2)


def order_total(lines, shipping=5.0, free_shipping_over=50.0):
    """Sum of line_total over (price, qty, discount_pct) lines; shipping is added unless the sum is AT LEAST
    free_shipping_over. Rounded to 2 decimals."""
    s = sum(line_total(*l) for l in lines)
    if s > free_shipping_over:
        return round(s, 2)
    return round(s + shipping, 2)
''',
      "test_inventory.py": "from inventory import Store, line_total\ns = Store(); s.add('a', 5)\ntry:\n    s.remove('a', 6)\n    raise SystemExit('remove should fail')\nexcept ValueError:\n    pass\nassert line_total(10, 3, 10) == 27.0\nprint('ok')\n"},
     """
from inventory import Store, line_total, order_total

def test_remove_too_many():
    s = Store(); s.add('a', 5)
    try:
        s.remove('a', 6)
    except ValueError:
        pass
    else:
        raise AssertionError('should raise')
    assert s.remove('a', 5) == 0

def test_stores_independent():
    a = Store(); a.add('x', 1); b = Store()
    assert 'x' not in b.items

def test_tags_independent():
    s = Store(); s.add('p', 1); s.add('q', 1); s.tag('p', 'red')
    assert s.tags('p') == ['red'] and s.tags('q') == []

def test_low_stock_inclusive():
    s = Store(); s.add('a', 2); s.add('b', 3); s.add('c', 9)
    assert s.low_stock(3) == ['a', 'b']

def test_round_half_up():
    assert line_total(0.125, 1) == 0.13 and line_total(2.675, 1) == 2.68 and line_total(1.005, 1) == 1.01

def test_free_shipping_at_threshold():
    assert order_total([(25, 2, 0)]) == 50.0 and order_total([(10, 1, 0)]) == 15.0

def test_discount():
    assert line_total(19.99, 3, 15) == 50.97
""",
     {"inventory/__init__.py": "from .store import Store\nfrom .pricing import line_total, order_total\n",
      "inventory/store.py": '''class Store:
    def __init__(self, items=None):
        self.items = dict(items or {})
        self._tags = {}

    def add(self, sku, qty, tags=None):
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.items[sku] = self.items.get(sku, 0) + qty
        self._tags.setdefault(sku, list(tags or []))
        return self.items[sku]

    def tag(self, sku, tag):
        self._tags.setdefault(sku, []).append(tag)

    def tags(self, sku):
        return self._tags.get(sku, [])

    def remove(self, sku, qty):
        have = self.items.get(sku, 0)
        if qty > have:
            raise ValueError("not enough stock")
        self.items[sku] = have - qty
        return self.items[sku]

    def low_stock(self, limit):
        return sorted(s for s, q in self.items.items() if q <= limit)
''',
      "inventory/pricing.py": '''from decimal import Decimal, ROUND_HALF_UP


def _r(x):
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def line_total(price, qty, discount_pct=0):
    d = Decimal(repr(price)) * qty * (1 - Decimal(repr(discount_pct)) / 100)
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def order_total(lines, shipping=5.0, free_shipping_over=50.0):
    s = sum(line_total(*l) for l in lines)
    if s >= free_shipping_over:
        return _r(s)
    return _r(s + shipping)
'''})

# ============================================================================ 12. extend an existing CLI
task("extend_todo", "extend",
     "todo.py is a small to-do manager used by test_todo.py. Add these features without breaking existing behaviour: "
     "(1) add(title, priority='normal', due=None) where priority is 'low'|'normal'|'high' (anything else raises "
     "ValueError) and due is an optional 'YYYY-MM-DD' string (invalid dates raise ValueError); (2) list_items(sort='id') "
     "also accepts sort='priority' (high, normal, low, then by id) and sort='due' (items with a due date first by date, "
     "then items without due date, ties by id); (3) overdue(today) returns open (not done) items with due < today, sorted "
     "by due; (4) the command line gains `python todo.py add TITLE [--priority P] [--due D]` and `python todo.py list "
     "[--sort S]`, storing data in the JSON file given by --db (default todo.json). Each listed line must be "
     "'ID [x] TITLE' or 'ID [ ] TITLE' followed by ' !high' or ' !low' when the priority is not normal and ' (due D)' "
     "when there is a due date.",
     {"todo.py": '''import json
import sys


class Todo:
    def __init__(self, items=None):
        self.items = items or []

    def add(self, title):
        item = {"id": len(self.items) + 1, "title": title, "done": False}
        self.items.append(item)
        return item

    def done(self, item_id):
        for it in self.items:
            if it["id"] == item_id:
                it["done"] = True
                return True
        return False

    def list_items(self, sort="id"):
        return sorted(self.items, key=lambda it: it["id"])


def fmt(it):
    return f"{it['id']} [{'x' if it['done'] else ' '}] {it['title']}"


def main(argv):
    db = "todo.json"
    if "--db" in argv:
        i = argv.index("--db")
        db = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    try:
        with open(db, encoding="utf-8") as f:
            t = Todo(json.load(f))
    except FileNotFoundError:
        t = Todo()
    cmd = argv[0] if argv else "list"
    if cmd == "add":
        it = t.add(" ".join(argv[1:]))
        print(fmt(it))
    elif cmd == "done":
        t.done(int(argv[1]))
    elif cmd == "list":
        for it in t.list_items():
            print(fmt(it))
    with open(db, "w", encoding="utf-8") as f:
        json.dump(t.items, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
''',
      "test_todo.py": "from todo import Todo\nt = Todo(); a = t.add('milk'); t.add('bread'); t.done(1)\nassert [i['title'] for i in t.list_items()] == ['milk', 'bread'] and t.items[0]['done']\nprint('ok')\n"},
     """
from todo import Todo
import os

def test_old_behaviour():
    t = Todo(); t.add('milk'); t.add('bread'); assert t.done(2) and not t.done(9)
    assert [i['title'] for i in t.list_items()] == ['milk', 'bread'] and t.items[1]['done']

def test_priority_validation():
    t = Todo()
    try:
        t.add('x', priority='urgent')
    except ValueError:
        pass
    else:
        raise AssertionError('no ValueError')

def test_due_validation():
    t = Todo()
    for bad in ('2026-02-30', '26-1-1', 'tomorrow'):
        try:
            t.add('x', due=bad)
        except ValueError:
            pass
        else:
            raise AssertionError('no ValueError for ' + bad)

def test_sort_priority():
    t = Todo(); t.add('a', 'low'); t.add('b'); t.add('c', 'high'); t.add('d', 'high')
    assert [i['title'] for i in t.list_items(sort='priority')] == ['c', 'd', 'b', 'a']

def test_sort_due():
    t = Todo(); t.add('a'); t.add('b', due='2026-05-01'); t.add('c', due='2026-01-09'); t.add('d')
    assert [i['title'] for i in t.list_items(sort='due')] == ['c', 'b', 'a', 'd']

def test_overdue():
    t = Todo(); t.add('a', due='2026-01-01'); t.add('b', due='2026-03-01'); t.add('c', due='2025-12-01'); t.add('d')
    t.done(3)
    assert [i['title'] for i in t.overdue('2026-02-01')] == ['a']

def test_cli_add_list():
    db = 'cli_test.json'
    if os.path.exists(db):
        os.remove(db)
    run_cli(['todo.py', 'add', 'Pay', 'rent', '--priority', 'high', '--due', '2026-11-01', '--db', db])
    run_cli(['todo.py', 'add', 'Walk', '--db', db])
    run_cli(['todo.py', 'add', 'Nap', '--priority', 'low', '--db', db])
    out = run_cli(['todo.py', 'list', '--sort', 'priority', '--db', db]).stdout.strip().splitlines()
    assert out == ['1 [ ] Pay rent !high (due 2026-11-01)', '2 [ ] Walk', '3 [ ] Nap !low']

def test_cli_old_commands():
    db = 'cli_test2.json'
    if os.path.exists(db):
        os.remove(db)
    run_cli(['todo.py', 'add', 'one', '--db', db]); run_cli(['todo.py', 'done', '1', '--db', db])
    assert run_cli(['todo.py', 'list', '--db', db]).stdout.strip() == '1 [x] one'
""",
     {"todo.py": '''import argparse
import datetime as dt
import json
import sys

PRI = {"high": 0, "normal": 1, "low": 2}


def _check_due(due):
    if due is None:
        return None
    try:
        if len(due) != 10:
            raise ValueError
        dt.date.fromisoformat(due)
    except (TypeError, ValueError):
        raise ValueError(f"bad due date {due!r}")
    return due


class Todo:
    def __init__(self, items=None):
        self.items = items or []

    def add(self, title, priority="normal", due=None):
        if priority not in PRI:
            raise ValueError("bad priority")
        item = {"id": len(self.items) + 1, "title": title, "done": False, "priority": priority, "due": _check_due(due)}
        self.items.append(item)
        return item

    def done(self, item_id):
        for it in self.items:
            if it["id"] == item_id:
                it["done"] = True
                return True
        return False

    def list_items(self, sort="id"):
        if sort == "priority":
            return sorted(self.items, key=lambda it: (PRI[it.get("priority", "normal")], it["id"]))
        if sort == "due":
            return sorted(self.items, key=lambda it: (it.get("due") is None, it.get("due") or "", it["id"]))
        return sorted(self.items, key=lambda it: it["id"])

    def overdue(self, today):
        return sorted((it for it in self.items if not it["done"] and it.get("due") and it["due"] < today),
                      key=lambda it: it["due"])


def fmt(it):
    s = f"{it['id']} [{'x' if it['done'] else ' '}] {it['title']}"
    if it.get("priority", "normal") != "normal":
        s += f" !{it['priority']}"
    if it.get("due"):
        s += f" (due {it['due']})"
    return s


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="todo.json")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("title", nargs="+")
    a.add_argument("--priority", default="normal")
    a.add_argument("--due")
    d = sub.add_parser("done")
    d.add_argument("id", type=int)
    l = sub.add_parser("list")
    l.add_argument("--sort", default="id")
    if "--db" in argv:
        i = argv.index("--db")
        argv = argv[i:i + 2] + argv[:i] + argv[i + 2:]
    args = p.parse_args(argv)
    try:
        with open(args.db, encoding="utf-8") as f:
            t = Todo(json.load(f))
    except FileNotFoundError:
        t = Todo()
    if args.cmd == "add":
        print(fmt(t.add(" ".join(args.title), args.priority, args.due)))
    elif args.cmd == "done":
        t.done(args.id)
    else:
        for it in t.list_items(getattr(args, "sort", "id")):
            print(fmt(it))
    with open(args.db, "w", encoding="utf-8") as f:
        json.dump(t.items, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''})

# ============================================================================ 13. refactor keeping behaviour
_LEGACY = '''def process(orders):
    # orders: list of dicts with keys id, customer, items (list of (name, price, qty)), coupon (str or None), country
    out = []
    for o in orders:
        if not o.get("items"):
            continue
        sub = 0
        for it in o["items"]:
            if it[2] > 0 and it[1] >= 0:
                sub = sub + it[1] * it[2]
        if sub == 0:
            continue
        disc = 0
        if o.get("coupon") == "SAVE10":
            disc = sub * 0.10
        elif o.get("coupon") == "SAVE20":
            if sub >= 100:
                disc = sub * 0.20
            else:
                disc = sub * 0.10
        elif o.get("coupon") == "FLAT5":
            disc = 5 if sub > 5 else sub
        net = sub - disc
        if o.get("country") == "US":
            tax = net * 0.07
        elif o.get("country") == "DE":
            tax = net * 0.19
        elif o.get("country") == "UK":
            tax = net * 0.20
        else:
            tax = 0
        if net >= 50:
            ship = 0
        else:
            if o.get("country") in ("US", "UK", "DE"):
                ship = 4.99
            else:
                ship = 14.99
        total = round(net + tax + ship, 2)
        level = "small"
        if total > 200:
            level = "large"
        elif total > 75:
            level = "medium"
        out.append({"id": o["id"], "customer": o["customer"].strip().title(), "subtotal": round(sub, 2),
                    "discount": round(disc, 2), "tax": round(tax, 2), "shipping": ship, "total": total, "level": level})
    out.sort(key=lambda r: (-r["total"], r["id"]))
    return out
'''
task("refactor_orders", "refactor",
     "orders.py has one long function process(orders). Refactor it into small, clearly named helper functions so that "
     "NO function in orders.py is longer than 20 lines (def line included) and none has more than 3 levels of nested "
     "blocks, while keeping process(orders) returning exactly the same results for every input. Add test_orders.py "
     "with a few tests of your own.",
     {"orders.py": _LEGACY},
     """
import ast, random, inspect
import orders

LEGACY = %r
ns = {}
exec(LEGACY, ns)
ref = ns['process']

def rand_orders(seed):
    r = random.Random(seed)
    res = []
    for i in range(40):
        items = [(r.choice('abcde'), round(r.uniform(-5, 80), 2), r.randint(-1, 4)) for _ in range(r.randint(0, 4))]
        res.append({'id': r.randint(1, 30), 'customer': r.choice(['  ann lee', 'BOB', 'cy d ']), 'items': items,
                    'coupon': r.choice([None, 'SAVE10', 'SAVE20', 'FLAT5', 'BOGUS']), 'country': r.choice(['US', 'DE', 'UK', 'FR', None])})
    return res

def same(a, b):
    # equal results; money values may differ by one cent (float summation order, e.g. sum() vs a loop)
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x.keys() != y.keys():
            return False
        for k in x:
            if isinstance(x[k], (int, float)) and isinstance(y[k], (int, float)):
                if abs(x[k] - y[k]) > 0.0101:
                    return False
            elif x[k] != y[k]:
                return False
    return True

def test_same_results_random():
    for seed in range(30):
        o = rand_orders(seed)
        assert same(orders.process([dict(x) for x in o]), ref([dict(x) for x in o])), seed

def test_edge_cases():
    o = [{'id': 1, 'customer': 'x', 'items': [], 'coupon': None, 'country': 'US'},
         {'id': 2, 'customer': 'y', 'items': [('a', 3, 1)], 'coupon': 'FLAT5', 'country': 'US'},
         {'id': 3, 'customer': 'z', 'items': [('a', 50, 2)], 'coupon': 'SAVE20', 'country': 'DE'}]
    assert same(orders.process(o), ref(o))

def _funcs():
    tree = ast.parse(inspect.getsource(orders))
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

def test_short_functions():
    fs = _funcs()
    assert len(fs) >= 4 and all(f.end_lineno - f.lineno + 1 <= 20 for f in fs)

def _depth(node, d=0):
    blocks = (ast.If, ast.For, ast.While, ast.With, ast.Try)
    best = d
    for c in ast.iter_child_nodes(node):
        best = max(best, _depth(c, d + 1 if isinstance(c, blocks) else d))
    return best

def test_shallow_nesting():
    assert all(_depth(f) <= 3 for f in _funcs())
""" % _LEGACY,
     {"orders.py": '''TAX = {"US": 0.07, "DE": 0.19, "UK": 0.20}


def subtotal(items):
    return sum(price * qty for _, price, qty in items if qty > 0 and price >= 0)


def discount(sub, coupon):
    if coupon == "SAVE10":
        return sub * 0.10
    if coupon == "SAVE20":
        return sub * (0.20 if sub >= 100 else 0.10)
    if coupon == "FLAT5":
        return 5 if sub > 5 else sub
    return 0


def shipping(net, country):
    if net >= 50:
        return 0
    return 4.99 if country in ("US", "UK", "DE") else 14.99


def level(total):
    if total > 200:
        return "large"
    return "medium" if total > 75 else "small"


def summarize(o):
    sub = subtotal(o["items"])
    if sub == 0:
        return None
    disc = discount(sub, o.get("coupon"))
    net = sub - disc
    tax = net * TAX.get(o.get("country"), 0)
    ship = shipping(net, o.get("country"))
    total = round(net + tax + ship, 2)
    return {"id": o["id"], "customer": o["customer"].strip().title(), "subtotal": round(sub, 2),
            "discount": round(disc, 2), "tax": round(tax, 2), "shipping": ship, "total": total, "level": level(total)}


def process(orders):
    out = [r for r in (summarize(o) for o in orders if o.get("items")) if r]
    out.sort(key=lambda r: (-r["total"], r["id"]))
    return out
''', "test_orders.py": "from orders import process\nassert process([]) == []\nprint('ok')\n"})

# ============================================================================ 14. performance
task("perf_pairs", "fix",
     "pairs.py works but is far too slow for real data (lists of 200,000 numbers). Make count_pairs, closest_pair_sum "
     "and longest_unique_run fast (roughly O(n) or O(n log n)) while returning exactly the same results as now. Keep "
     "the function names and signatures. Visible test: test_pairs.py.",
     {"pairs.py": '''def count_pairs(nums, target):
    """Number of index pairs i < j with nums[i] + nums[j] == target."""
    n = 0
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                n += 1
    return n


def closest_pair_sum(nums, target):
    """The sum nums[i] + nums[j] (i < j) closest to target; on a tie the smaller sum. None if fewer than 2 numbers."""
    best = None
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            s = nums[i] + nums[j]
            if best is None or abs(s - target) < abs(best - target) or (abs(s - target) == abs(best - target) and s < best):
                best = s
    return best


def longest_unique_run(nums):
    """Length of the longest contiguous slice with no repeated value."""
    best = 0
    for i in range(len(nums)):
        seen = set()
        for j in range(i, len(nums)):
            if nums[j] in seen:
                break
            seen.add(nums[j])
        best = max(best, len(seen))
    return best
''', "test_pairs.py": "from pairs import count_pairs, closest_pair_sum, longest_unique_run\nassert count_pairs([1, 2, 3, 4, 3], 6) == 2\nassert closest_pair_sum([1, 5, 9], 12) == 14 - 0 or True\nassert longest_unique_run([1, 2, 1, 3, 4]) == 4\nprint('ok')\n"},
     """
import random, time
from pairs import count_pairs, closest_pair_sum, longest_unique_run

def slow_count(nums, t):
    return sum(1 for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] + nums[j] == t)

def slow_close(nums, t):
    best = None
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            s = nums[i] + nums[j]
            if best is None or abs(s - t) < abs(best - t) or (abs(s - t) == abs(best - t) and s < best):
                best = s
    return best

def slow_run(nums):
    best = 0
    for i in range(len(nums)):
        seen = set()
        for j in range(i, len(nums)):
            if nums[j] in seen:
                break
            seen.add(nums[j])
        best = max(best, len(seen))
    return best

def test_count_small_random():
    r = random.Random(1)
    for _ in range(200):
        a = [r.randint(-5, 5) for _ in range(r.randint(0, 12))]; t = r.randint(-6, 6)
        assert count_pairs(a, t) == slow_count(a, t)

def test_close_small_random():
    r = random.Random(2)
    for _ in range(200):
        a = [r.randint(-20, 20) for _ in range(r.randint(0, 10))]; t = r.randint(-30, 30)
        assert closest_pair_sum(a, t) == slow_close(a, t)

def test_run_small_random():
    r = random.Random(3)
    for _ in range(200):
        a = [r.randint(0, 6) for _ in range(r.randint(0, 15))]
        assert longest_unique_run(a) == slow_run(a)

def test_big_fast():
    r = random.Random(4)
    a = [r.randint(-10**6, 10**6) for _ in range(200000)]
    t0 = time.time()
    count_pairs(a, 1234); closest_pair_sum(a, 777); longest_unique_run([x % 50000 for x in a])
    assert time.time() - t0 < 5.0

def test_big_duplicates():
    a = [7] * 100000
    t0 = time.time()
    assert count_pairs(a, 14) == 100000 * 99999 // 2 and longest_unique_run(a) == 1 and closest_pair_sum(a, 0) == 14
    assert time.time() - t0 < 5.0
""",
     {"pairs.py": '''from collections import Counter


def count_pairs(nums, target):
    seen, n = Counter(), 0
    for x in nums:
        n += seen[target - x]
        seen[x] += 1
    return n


def closest_pair_sum(nums, target):
    if len(nums) < 2:
        return None
    a = sorted(nums)
    i, j, best = 0, len(a) - 1, None
    while i < j:
        s = a[i] + a[j]
        if best is None or abs(s - target) < abs(best - target) or (abs(s - target) == abs(best - target) and s < best):
            best = s
        if s < target:
            i += 1
        elif s > target:
            j -= 1
        else:
            return s
    return best


def longest_unique_run(nums):
    last, start, best = {}, 0, 0
    for i, x in enumerate(nums):
        if x in last and last[x] >= start:
            start = last[x] + 1
        last[x] = i
        best = max(best, i - start + 1)
    return best
'''})

# ============================================================================ 15. multi-file package with CLI
task("textstats_pkg", "build",
     "Create a Python package textstats (folder textstats/ with __init__.py, core.py and __main__.py). core.py: "
     "words(text) -> list of lowercase words (letters, digits and apostrophes inside words, e.g. don't; split on "
     "everything else; Unicode letters like é count as letters), top_words(text, n, stop=None) -> list of (word, count) "
     "sorted by count desc then word asc, skipping words in the stop set, and summary(text) -> dict with keys words "
     "(count), unique, sentences (count of runs ending in . ! or ?; trailing text without punctuation counts as one more "
     "sentence if it has a word), avg_word_len (rounded to 2). __init__.py exports those three. `python -m textstats "
     "FILE [--top N] [--stop FILE]` prints the summary as 'key: value' lines in the order words, unique, sentences, "
     "avg_word_len, then a blank line, then the top N (default 5) as 'word count' lines. A missing FILE exits with "
     "code 1 and a message on stderr. sample.txt is an example input.",
     {"sample.txt": "The cat sat. The cat ran! Did the dog see the cat?\nDon't worry, café owners said\n"},
     """
from textstats import words, top_words, summary
import os

def test_words():
    assert words("Don't stop, CAFÉ-au-lait 42x!") == ["don't", 'stop', 'café', 'au', 'lait', '42x']

def test_words_apostrophe_edges():
    assert words("'quoted' rock'n'roll") == ['quoted', "rock'n'roll"]

def test_top_words():
    t = 'b a c b a b d'
    assert top_words(t, 2) == [('b', 3), ('a', 2)] and top_words(t, 10, stop={'b'}) == [('a', 2), ('c', 1), ('d', 1)]

def test_summary():
    s = summary(open('sample.txt', encoding='utf-8').read())
    assert s == {'words': 17, 'unique': 12, 'sentences': 4, 'avg_word_len': round(sum(map(len, words(open('sample.txt', encoding='utf-8').read()))) / 17, 2)}

def test_summary_empty():
    s = summary('')
    assert s['words'] == 0 and s['sentences'] == 0 and s['avg_word_len'] == 0

def test_cli():
    r = run_cli(['-m', 'textstats', 'sample.txt', '--top', '2'])
    lines = r.stdout.splitlines()
    assert r.returncode == 0 and lines[:4] == ['words: 17', 'unique: 12', 'sentences: 4', lines[3]] and lines[3].startswith('avg_word_len: ')
    assert lines[4] == '' and lines[5:] == ['the 4', 'cat 3']

def test_cli_stop():
    with open('stop.txt', 'w', encoding='utf-8') as f:
        f.write('the\\ncat\\n')
    r = run_cli(['-m', 'textstats', 'sample.txt', '--top', '1', '--stop', 'stop.txt'])
    assert r.stdout.splitlines()[-1] in ("café 1", "did 1", "don't 1")

def test_cli_missing():
    r = run_cli(['-m', 'textstats', 'missing.txt'])
    assert r.returncode == 1 and r.stderr.strip()
""",
     {"textstats/__init__.py": "from .core import words, top_words, summary\n",
      "textstats/core.py": '''import re
from collections import Counter

_W = re.compile(r"[^\\W_]+(?:'[^\\W_]+)*")


def words(text):
    return [w.lower() for w in _W.findall(text)]


def top_words(text, n, stop=None):
    stop = stop or set()
    c = Counter(w for w in words(text) if w not in stop)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def summary(text):
    ws = words(text)
    parts = re.split(r"[.!?]+", text)
    sentences = sum(1 for p in parts[:-1] if words(p)) + (1 if words(parts[-1]) else 0)
    return {"words": len(ws), "unique": len(set(ws)), "sentences": sentences,
            "avg_word_len": round(sum(map(len, ws)) / len(ws), 2) if ws else 0}
''',
      "textstats/__main__.py": '''import argparse
import sys

from .core import summary, top_words


def main(argv=None):
    p = argparse.ArgumentParser(prog="textstats")
    p.add_argument("file")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--stop")
    a = p.parse_args(argv)
    try:
        text = open(a.file, encoding="utf-8").read()
        stop = set(open(a.stop, encoding="utf-8").read().split()) if a.stop else None
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for k, v in summary(text).items():
        print(f"{k}: {v}")
    print()
    for w, c in top_words(text, a.top, stop):
        print(f"{w} {c}")
    return 0


sys.exit(main())
'''})

# ============================================================================ 16. asyncio
task("async_limit", "build",
     "Create fetcher.py with: async gather_limited(factories, limit) where factories is a list of zero-argument "
     "functions that each return an awaitable. Run them with at most limit running at the same time, and return a "
     "list of results in the SAME order as factories; if one raises an exception, put the exception object in its place "
     "instead of failing the whole call. limit < 1 raises ValueError. Also add async retry(factory, attempts=3, "
     "base_delay=0.1) that awaits factory() and on an exception waits base_delay * 2**k (k = 0, 1, ...) before trying "
     "again, re-raising the last exception after attempts tries; use asyncio.sleep for waiting. Visible test: "
     "test_fetcher.py.",
     {"test_fetcher.py": "import asyncio\nfrom fetcher import gather_limited\nasync def one(): return 1\n"
                         "assert asyncio.run(gather_limited([one, one], 1)) == [1, 1]\nprint('ok')\n"},
     """
import asyncio, time
import fetcher
from fetcher import gather_limited, retry

def test_order():
    async def make(i, d):
        await asyncio.sleep(d); return i
    fs = [lambda i=i: make(i, (5 - i) * 0.01) for i in range(5)]
    assert asyncio.run(gather_limited(fs, 3)) == [0, 1, 2, 3, 4]

def test_limit_respected():
    state = {'now': 0, 'max': 0}
    async def job():
        state['now'] += 1; state['max'] = max(state['max'], state['now'])
        await asyncio.sleep(0.02); state['now'] -= 1; return 'ok'
    res = asyncio.run(gather_limited([job] * 12, 3))
    assert res == ['ok'] * 12 and state['max'] == 3

def test_parallel_speed():
    async def job():
        await asyncio.sleep(0.2); return 1
    t = time.time(); asyncio.run(gather_limited([job] * 10, 10))
    assert time.time() - t < 0.6

def test_exceptions_in_place():
    async def ok(): return 'y'
    async def bad(): raise KeyError('boom')
    res = asyncio.run(gather_limited([ok, bad, ok], 2))
    assert res[0] == 'y' and isinstance(res[1], KeyError) and res[2] == 'y'

def test_limit_validation():
    try:
        asyncio.run(gather_limited([], 0))
    except ValueError:
        pass
    else:
        raise AssertionError('no ValueError')

def test_empty():
    assert asyncio.run(gather_limited([], 4)) == []

def test_retry_success_and_delays():
    calls, sleeps = [], []
    real = asyncio.sleep
    async def fake_sleep(d, *a, **k):
        sleeps.append(d); await real(0)
    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError('x')
        return 'done'
    fetcher.asyncio.sleep = fake_sleep
    try:
        assert asyncio.run(retry(flaky, attempts=5, base_delay=0.5)) == 'done'
    finally:
        fetcher.asyncio.sleep = real
    assert len(calls) == 3 and sleeps == [0.5, 1.0]

def test_retry_gives_up():
    n = []
    async def always():
        n.append(1); raise ValueError('nope')
    try:
        asyncio.run(retry(always, attempts=3, base_delay=0.001))
    except ValueError:
        pass
    else:
        raise AssertionError('should re-raise')
    assert len(n) == 3
""",
     {"fetcher.py": '''import asyncio


async def gather_limited(factories, limit):
    if limit < 1:
        raise ValueError("limit must be >= 1")
    sem = asyncio.Semaphore(limit)
    results = [None] * len(factories)

    async def run(i, f):
        async with sem:
            try:
                results[i] = await f()
            except Exception as e:
                results[i] = e

    await asyncio.gather(*(run(i, f) for i, f in enumerate(factories)))
    return results


async def retry(factory, attempts=3, base_delay=0.1):
    for k in range(attempts):
        try:
            return await factory()
        except Exception:
            if k == attempts - 1:
                raise
            await asyncio.sleep(base_delay * 2 ** k)
'''})
