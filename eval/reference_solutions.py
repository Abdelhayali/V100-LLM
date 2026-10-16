"""Reference solutions for tasks_hard.CODING: `python eval/reference_solutions.py` proves every hidden test is satisfiable."""
REF = {}

REF["calc"] = r'''
def evaluate(expr):
    s = expr.replace(" ", ""); i = 0
    def num():
        nonlocal i
        j = i
        while i < len(s) and (s[i].isdigit() or s[i] == "."): i += 1
        return float(s[j:i])
    def factor():
        nonlocal i
        if s[i] == "-": i += 1; return -factor()
        if s[i] == "+": i += 1; return factor()
        if s[i] == "(":
            i += 1; v = expr_(); i += 1; return v
        return num()
    def term():
        nonlocal i
        v = factor()
        while i < len(s) and s[i] in "*/":
            op = s[i]; i += 1; r = factor(); v = v * r if op == "*" else v / r
        return v
    def expr_():
        nonlocal i
        v = term()
        while i < len(s) and s[i] in "+-":
            op = s[i]; i += 1; r = term(); v = v + r if op == "+" else v - r
        return v
    return expr_()
'''
REF["regex"] = r'''
from functools import lru_cache
def match(p, t):
    @lru_cache(None)
    def f(i, j):
        if i == len(p): return j == len(t)
        first = j < len(t) and p[i] in (t[j], ".")
        if i + 1 < len(p) and p[i + 1] == "*":
            return f(i + 2, j) or (first and f(i, j + 1))
        return first and f(i + 1, j + 1)
    return f(0, 0)
'''
REF["dijkstra_path"] = r'''
import heapq
def shortest(g, s, t):
    pq = [(0, [s])]; done = set()
    while pq:
        d, path = heapq.heappop(pq); u = path[-1]
        if u in done: continue
        done.add(u)
        if u == t: return (d, path)
        for v, w in g.get(u, {}).items():
            if v not in done: heapq.heappush(pq, (d + w, path + [v]))
    return (-1, [])
'''
REF["intervals"] = r'''
def max_non_overlapping(iv):
    n, end = 0, float("-inf")
    for a, b in sorted(iv, key=lambda x: x[1]):
        if a >= end: n += 1; end = b
    return n
'''
REF["bigmul"] = r'''
def multiply(a, b):
    a, b = a.lstrip("0") or "0", b.lstrip("0") or "0"
    r = [0] * (len(a) + len(b))
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            r[i + j + 1] += (ord(a[i]) - 48) * (ord(b[j]) - 48)
    for k in range(len(r) - 1, 0, -1):
        r[k - 1] += r[k] // 10; r[k] %= 10
    return "".join(map(str, r)).lstrip("0") or "0"
'''
REF["lru_ttl"] = r'''
from collections import OrderedDict
class TTLCache:
    def __init__(self, capacity): self.c = capacity; self.d = OrderedDict()
    def get(self, k, now):
        if k not in self.d: return None
        v, exp = self.d[k]
        if now >= exp: del self.d[k]; return None
        self.d.move_to_end(k); return v
    def put(self, k, v, now, ttl):
        if k in self.d: del self.d[k]
        if len(self.d) >= self.c:
            for kk in [kk for kk, (_, e) in self.d.items() if now >= e]: del self.d[kk]
        if len(self.d) >= self.c: self.d.popitem(last=False)
        self.d[k] = (v, now + ttl)
'''
REF["topo"] = r'''
import heapq
def course_order(n, pre):
    indeg = [0] * n; adj = [[] for _ in range(n)]
    for a, b in pre: adj[b].append(a); indeg[a] += 1
    h = [i for i in range(n) if indeg[i] == 0]; heapq.heapify(h); out = []
    while h:
        u = heapq.heappop(h); out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0: heapq.heappush(h, v)
    return out if len(out) == n else []
'''
REF["edit"] = r'''
def edit_ops(a, b):
    n, m = len(a), len(b); d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): d[i][0] = i
    for j in range(m + 1): d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1, d[i-1][j-1] + (a[i-1] != b[j-1]))
            if i > 1 and j > 1 and a[i-1] == b[j-2] and a[i-2] == b[j-1]: d[i][j] = min(d[i][j], d[i-2][j-2] + 1)
    return d[n][m]
'''
REF["roman_parse"] = r'''
def from_roman(s):
    def to(n):
        out = ""
        for v, r in [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]:
            while n >= v: out += r; n -= v
        return out
    val = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    if not s or any(c not in val for c in s): raise ValueError(s)
    t = 0
    for i, c in enumerate(s):
        t += -val[c] if i + 1 < len(s) and val[c] < val[s[i+1]] else val[c]
    if not 0 < t < 4000 or to(t) != s: raise ValueError(s)
    return t
'''
REF["days"] = r'''
def days_between(d1, d2):
    def n(d):
        y, m, dd = map(int, d.split("-"))
        if m <= 2: y -= 1; m += 12
        return 365 * y + y // 4 - y // 100 + y // 400 + (153 * (m - 3) + 2) // 5 + dd
    return abs(n(d1) - n(d2))
'''
REF["sudoku"] = r'''
def solve(g):
    def ok(r, c, v):
        if v in g[r] or any(g[i][c] == v for i in range(9)): return False
        br, bc = 3 * (r // 3), 3 * (c // 3)
        return all(g[i][j] != v for i in range(br, br + 3) for j in range(bc, bc + 3))
    def rec():
        for r in range(9):
            for c in range(9):
                if g[r][c] == 0:
                    for v in range(1, 10):
                        if ok(r, c, v):
                            g[r][c] = v
                            if rec(): return True
                            g[r][c] = 0
                    return False
        return True
    rec(); return g
'''
REF["trie"] = r'''
class Autocomplete:
    def __init__(self): self.w = {}
    def add(self, word, weight): self.w[word] = self.w.get(word, 0) + weight
    def top(self, prefix, k):
        return sorted((w for w in self.w if w.startswith(prefix)), key=lambda w: (-self.w[w], w))[:k]
'''
REF["knapsack"] = r'''
from itertools import combinations
def best_items(items, cap):
    best = (0, [])
    for r in range(len(items) + 1):
        for c in combinations(items, r):
            if sum(x[1] for x in c) <= cap:
                v = sum(x[2] for x in c); names = sorted(x[0] for x in c)
                if v > best[0] or (v == best[0] and names < best[1]): best = (v, names)
    return best
'''
REF["rle"] = r'''
import re
def encode(s):
    return "".join((str(len(m.group(0))) if len(m.group(0)) > 1 else "") + m.group(1) for m in re.finditer(r"(.)\1*", s))
def decode(s):
    return "".join(ch * int(n or 1) for n, ch in re.findall(r"(\d*)(\D)", s))
'''
REF["spiral_gen"] = r'''
def spiral_matrix(n):
    m = [[0] * n for _ in range(n)]; r = c = 0; dr, dc = 0, 1
    for k in range(1, n * n + 1):
        m[r][c] = k
        if not (0 <= r + dr < n and 0 <= c + dc < n and m[r + dr][c + dc] == 0): dr, dc = dc, -dr
        r += dr; c += dc
    return m
def diag_sum(m):
    n = len(m)
    return sum(m[i][i] + m[i][n - 1 - i] for i in range(n)) - (m[n // 2][n // 2] if n % 2 else 0)
'''
REF["json_min"] = r'''
def parse(s):
    i = 0
    def ws():
        nonlocal i
        while i < len(s) and s[i] in " \t\n\r": i += 1
    def val():
        nonlocal i
        ws(); c = s[i]
        if c == "{":
            i += 1; out = {}; ws()
            if s[i] == "}": i += 1; return out
            while True:
                ws(); k = val(); ws(); i += 1; out[k] = val(); ws()
                if s[i] == ",": i += 1; continue
                i += 1; return out
        if c == "[":
            i += 1; out = []; ws()
            if s[i] == "]": i += 1; return out
            while True:
                out.append(val()); ws()
                if s[i] == ",": i += 1; continue
                i += 1; return out
        if c == '"':
            i += 1; out = ""
            while s[i] != '"':
                if s[i] == "\\": i += 1
                out += s[i]; i += 1
            i += 1; return out
        for lit, v in (("true", True), ("false", False), ("null", None)):
            if s.startswith(lit, i): i += len(lit); return v
        j = i
        if s[i] == "-": i += 1
        while i < len(s) and s[i].isdigit(): i += 1
        return int(s[j:i])
    return val()
'''

if __name__ == "__main__":
    import subprocess, sys, tempfile
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tasks_hard as H
    bad = 0
    for name, _, tests in H.CODING:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(REF[name] + "\n" + tests + "\n"); p = f.name
        r = subprocess.run([sys.executable, "-I", p], capture_output=True, text=True, timeout=60)
        Path(p).unlink()
        print(("ok  " if r.returncode == 0 else "FAIL") + " " + name + ("" if r.returncode == 0 else "  " + r.stderr.strip().splitlines()[-1]))
        bad += r.returncode != 0
    sys.exit(bad)
