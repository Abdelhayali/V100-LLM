"""
V100-LLM evaluation v2 ("hard"). Designed so that no 16 GB-class model scores 100: multi-step reasoning, edge-case unit
tests, multi-constraint instructions, multi-hop tool use, longer agent tasks, harder vision and multi-needle long context.
Every answer below is computed by code (see the asserts at the bottom); nothing is graded by an LLM.
"""
import datetime as _dt

# ============================================================================ coding (hidden edge-case tests)
CODING = [
    ("calc", "Write `evaluate(expr: str) -> float` that evaluates an arithmetic expression with + - * / and parentheses, "
             "respecting precedence and left-to-right associativity, unary minus (e.g. '-3*-2'), integers and decimals, "
             "and arbitrary spaces. Do not use eval/exec/ast.",
     "assert abs(evaluate('2+3*4') - 14) < 1e-9\nassert abs(evaluate('(2+3)*4') - 20) < 1e-9\nassert abs(evaluate('10-4-3') - 3) < 1e-9\n"
     "assert abs(evaluate('8/4/2') - 1) < 1e-9\nassert abs(evaluate('-3*-2') - 6) < 1e-9\nassert abs(evaluate(' 1.5 * ( 2 - -2 ) ') - 6) < 1e-9\n"
     "assert abs(evaluate('-(2+3)*2') + 10) < 1e-9\nimport inspect, sys\nsrc = inspect.getsource(sys.modules[__name__]) if False else ''"),
    ("regex", "Write `match(pattern: str, text: str) -> bool` implementing full-string regex matching with only '.' (any char) "
              "and '*' (zero or more of the preceding element). Do not use the re module.",
     "assert match('a*', '') and match('.*', 'abc') and match('c*a*b', 'aab') and match('mis*is*p*.', 'mississippi') is False\n"
     "assert not match('a', 'aa') and match('ab*c', 'ac') and not match('a.c', 'ac') and match('.*c', 'abc') and not match('a*b', 'aaa')"),
    ("dijkstra_path", "Write `shortest(graph: dict, s, t) -> tuple[int, list]` returning (distance, path) of the shortest path in a "
                      "weighted directed graph {node: {nbr: w}}. If several shortest paths exist, return the lexicographically "
                      "smallest path (compare node lists). Return (-1, []) if t is unreachable. Nodes may appear only as neighbours.",
     "g = {'a': {'b': 1, 'c': 1}, 'b': {'d': 1}, 'c': {'d': 1}, 'd': {}}\nassert shortest(g, 'a', 'd') == (2, ['a', 'b', 'd'])\n"
     "assert shortest(g, 'd', 'a') == (-1, [])\nassert shortest(g, 'a', 'a') == (0, ['a'])\n"
     "h = {'s': {'x': 5, 'y': 1}, 'y': {'x': 1, 'z': 7}, 'x': {'z': 1}}\nassert shortest(h, 's', 'z') == (3, ['s', 'y', 'x', 'z'])"),
    ("intervals", "Write `max_non_overlapping(iv: list[tuple[int,int]]) -> int` returning the maximum number of pairwise "
                  "non-overlapping half-open intervals [start, end).",
     "assert max_non_overlapping([(1,3),(2,4),(3,5)]) == 2\nassert max_non_overlapping([]) == 0\n"
     "assert max_non_overlapping([(1,2),(2,3),(3,4),(1,4)]) == 3\nassert max_non_overlapping([(5,9),(1,10),(2,3),(3,5)]) == 3"),
    ("bigmul", "Write `multiply(a: str, b: str) -> str` multiplying two non-negative integers given as decimal strings (up to "
               "500 digits) without converting the whole string to int. Return no leading zeros ('0' for zero).",
     "import random\nrandom.seed(7)\nfor _ in range(20):\n    x = str(random.randrange(10**random.randint(1,300)))\n    y = str(random.randrange(10**random.randint(1,300)))\n"
     "    assert multiply(x, y) == str(int(x) * int(y)), (x, y)\nassert multiply('0', '12345') == '0' and multiply('000', '7') == '0'"),
    ("lru_ttl", "Write a class `TTLCache(capacity: int)` with `put(key, value, now: int, ttl: int)` and `get(key, now: int)` "
                "(returns None if missing or expired; an entry put at time t with ttl d is valid while now < t + d). `get` "
                "counts as a use. When full, first drop expired entries, then evict the least recently used.",
     "c = TTLCache(2)\nc.put('a', 1, now=0, ttl=10); c.put('b', 2, now=1, ttl=2)\nassert c.get('a', now=2) == 1\nassert c.get('b', now=3) is None\n"
     "c.put('c', 3, now=4, ttl=10); c.put('d', 4, now=5, ttl=10)\nassert c.get('a', now=6) is None and c.get('c', now=6) == 3 and c.get('d', now=6) == 4\n"
     "c2 = TTLCache(2); c2.put('x', 1, 0, 100); c2.put('y', 2, 1, 100); c2.get('x', 2); c2.put('z', 3, 3, 100)\nassert c2.get('y', 4) is None and c2.get('x', 4) == 1"),
    ("topo", "Write `course_order(n: int, prereq: list[tuple[int,int]]) -> list[int]` where (a, b) means b must come before a. "
             "Return a valid order of 0..n-1 that is lexicographically smallest, or [] if impossible (cycle).",
     "assert course_order(4, [(1,0),(2,0),(3,1),(3,2)]) == [0,1,2,3]\nassert course_order(2, [(0,1),(1,0)]) == []\n"
     "assert course_order(3, []) == [0,1,2]\nassert course_order(5, [(0,4),(1,4),(2,0)]) == [3,4,0,1,2]"),
    ("edit", "Write `edit_ops(a: str, b: str) -> int` returning the minimum number of insertions, deletions and substitutions "
             "to turn a into b, where swapping two ADJACENT characters also counts as one operation.",
     "assert edit_ops('kitten', 'sitting') == 3 and edit_ops('ab', 'ba') == 1 and edit_ops('', 'abc') == 3\n"
     "assert edit_ops('abcdef', 'abdcef') == 1 and edit_ops('abcd', 'acbd') == 1 and edit_ops('same', 'same') == 0"),
    ("roman_parse", "Write `from_roman(s: str) -> int` converting a Roman numeral to an integer, and raise ValueError for invalid "
                    "numerals (e.g. 'IIII', 'VV', 'IC', 'MMMM', '', lowercase).",
     "assert from_roman('MCMXCIV') == 1994 and from_roman('MMMCMXCIX') == 3999 and from_roman('XLII') == 42\n"
     "for bad in ['IIII', 'VV', 'IC', 'MMMM', '', 'iv', 'XM', 'IIV']:\n    try:\n        from_roman(bad); raise AssertionError(bad)\n    except ValueError:\n        pass"),
    ("days", "Write `days_between(d1: str, d2: str) -> int` returning the absolute number of days between two dates 'YYYY-MM-DD' "
             "(Gregorian calendar, years 1600-2400). Do not use the datetime, time or calendar modules.",
     "assert days_between('2024-02-28', '2024-03-01') == 2 and days_between('1900-02-28', '1900-03-01') == 1\n"
     "assert days_between('2000-01-01', '2026-10-16') == 9785 and days_between('2026-10-16', '2000-01-01') == 9785 and days_between('1600-03-01', '2400-02-29') == 292193"),
    ("sudoku", "Write `solve(grid: list[list[int]]) -> list[list[int]]` solving a 9x9 sudoku (0 = empty) and returning the solved grid.",
     "p = [[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],[8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],[0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]]\n"
     "s = solve([r[:] for r in p])\nassert all(sorted(r) == list(range(1,10)) for r in s) and all(sorted(c) == list(range(1,10)) for c in zip(*s))\n"
     "assert all(sorted(s[r][c] for r in range(br, br+3) for c in range(bc, bc+3)) == list(range(1,10)) for br in (0,3,6) for bc in (0,3,6))\n"
     "assert all(p[r][c] in (0, s[r][c]) for r in range(9) for c in range(9))"),
    ("trie", "Write a class `Autocomplete` with `add(word: str, weight: int)` (re-adding a word adds to its weight) and "
             "`top(prefix: str, k: int) -> list[str]` returning up to k words with that prefix sorted by weight descending, "
             "then alphabetically.",
     "a = Autocomplete()\nfor w, n in [('car', 5), ('cart', 3), ('care', 5), ('cat', 1), ('dog', 9), ('cart', 3)]:\n    a.add(w, n)\n"
     "assert a.top('ca', 3) == ['cart', 'car', 'care'] and a.top('d', 5) == ['dog'] and a.top('x', 2) == [] and a.top('', 2) == ['dog', 'cart']"),
    ("knapsack", "Write `best_items(items: list[tuple[str,int,int]], cap: int) -> tuple[int, list[str]]` for 0/1 knapsack "
                 "(name, weight, value): return (max value, names of a best subset sorted alphabetically).",
     "v, names = best_items([('a',1,1),('b',3,4),('c',4,5),('d',5,7)], 7)\nassert v == 9 and names == ['b', 'c']\n"
     "assert best_items([], 10) == (0, []) and best_items([('x', 11, 100)], 10) == (0, [])"),
    ("rle", "Write `encode(s: str) -> str` and `decode(s: str) -> str` for run-length encoding where a run is written as "
            "<count><char> and the count is omitted when it is 1 (e.g. 'aaabcc' -> '3ab2c'). Characters are never digits. "
            "Runs longer than 9 must still round-trip.",
     "assert encode('aaabcc') == '3ab2c' and decode('3ab2c') == 'aaabcc' and encode('') == '' and decode('') == ''\n"
     "s = 'x' * 25 + 'y' + 'zz' * 1\nassert decode(encode(s)) == s and encode('x'*12) == '12x'"),
    ("spiral_gen", "Write `spiral_matrix(n: int) -> list[list[int]]` returning an n x n matrix filled with 1..n*n in clockwise "
                   "spiral order starting at the top-left, then `diag_sum(m)` returning the sum of both diagonals (centre counted once).",
     "assert spiral_matrix(3) == [[1,2,3],[8,9,4],[7,6,5]] and spiral_matrix(1) == [[1]]\nassert diag_sum(spiral_matrix(5)) == 133 and diag_sum(spiral_matrix(4)) == 80"),
    ("json_min", "Write `parse(s: str)` that parses a JSON subset: objects, arrays, double-quoted strings with \\\" and \\\\ "
                 "escapes, integers (possibly negative), true, false, null, and whitespace. Do not use the json module.",
     "assert parse('{\"a\": [1, -2, {\"b\": null}], \"c\": \"x\\\\\"y\", \"d\": true}') == {'a': [1, -2, {'b': None}], 'c': 'x\"y', 'd': True}\n"
     "assert parse(' [ ] ') == [] and parse('{}') == {} and parse('\"a\\\\\\\\b\"') == 'a\\\\b'"),
]

# ============================================================================ reasoning (exact answers)
REASONING = [
    ("A store raises a price by 20% and then lowers the new price by 25%. The final price is $45. What was the original price in dollars? Number only.", ["50"]),
    ("Tom is twice as old as Ann. In 6 years Tom will be 1.5 times as old as Ann. How old is Ann now? Number only.", ["6"]),
    ("A tank fills in 6 hours with pipe A and in 4 hours with pipe B. Pipe C drains a full tank in 12 hours. With all three open, how many hours to fill the empty tank? Number only.", ["3"]),
    ("How many integers from 1 to 1000 are divisible by 3 or 5 but not by 15? Number only.", ["401"]),
    ("What is the remainder when 7^2026 is divided by 10? Number only.", ["9"]),
    ("A clock shows 3:40. What is the smaller angle between the hour and minute hands, in degrees? Number only.", ["130"]),
    ("If 5 machines make 5 widgets in 5 minutes, how many minutes do 100 machines need to make 100 widgets? Number only.", ["5"]),
    ("A bag has 3 red and 5 blue balls. Two are drawn without replacement. What is the probability both are red? Answer as a reduced fraction a/b.", ["3/28"]),
    ("The sum of three consecutive odd integers is 159. What is the largest of them? Number only.", ["55"]),
    ("A car travels 120 km at 60 km/h and returns the same 120 km at 40 km/h. What is the average speed for the whole trip in km/h? Number only.", ["48"]),
    ("What day of the week was 1 January 2000? One word.", ["saturday"]),
    ("How many days are there from 15 March 2026 to 9 November 2026, counting neither endpoint? Number only.", ["238"]),
    ("Five people A, B, C, D, E sit in a row. A is not at either end. B sits immediately right of C. D sits at the far left. E is not next to D. C is in seat 2 counting from the left. Who sits in seat 4? One letter.", ["a"]),
    ("I am a three-digit number. My digits sum to 13, my hundreds digit is twice my units digit, and my tens digit is one more than my units digit. What number am I? Number only.", ["643"]),
    ("A rectangle's length is 3 more than twice its width, and its area is 65. What is its perimeter? Number only.", ["36"]),
    ("Each year a population grows by 10%. Starting from 10000, what is the population after 3 years? Number only (no commas).", ["13310"]),
    ("In a race, Ana finished ahead of Ben, Cara finished behind Dan, Ben finished ahead of Dan, and Eli finished last. Who finished second? One name.", ["ben"]),
    ("A sequence starts 2, 6, 12, 20, 30, ... What is the 10th term? Number only.", ["110"]),
    ("How many ways can the letters of the word LEVEL be arranged? Number only.", ["30"]),
    ("A shirt costs $40 after a 20% discount. Sales tax of 10% is then added. A customer pays with a $50 bill. How much change in dollars? Number only.", ["6"]),
]

# ============================================================================ instruction following (several rules at once)
# (prompt, [(checker, arg), ...]) - all rules must hold
IFEVAL = [
    ("Write exactly 3 sentences about the ocean. Every sentence must end with an exclamation mark and the word 'blue' must appear exactly twice in total.",
     [("sentences", 3), ("all_sentences_end", "!"), ("word_count_exact", ("blue", 2))]),
    ("List 5 programming languages as a JSON object whose keys are the names and whose values are the year each was first released (integers). Output only the JSON.",
     [("json_obj_len", 5), ("json_values_int", None)]),
    ("Write a haiku-like poem of exactly 3 lines about autumn, all in lowercase, without using the letter 'e'.",
     [("lines", 3), ("lowercase", None), ("no_char", "e")]),
    ("Answer with exactly two paragraphs separated by a line containing only ***. The first paragraph must start with the word 'First' and the second with 'Second'. Topic: why sleep matters.",
     [("paragraphs_sep", ("***", 2)), ("para_starts", ["First", "Second"])]),
    ("Give 4 tips for studying as a numbered list (1. 2. 3. 4.), each tip at most 8 words, and end your answer with the line 'Good luck!'",
     [("numbered", 4), ("max_words_per_item", 8), ("endswith", "Good luck!")]),
    ("Write a title for an article about solar energy. It must be in Title Case, contain exactly 5 words, and be wrapped in double square brackets like [[Title]]. Output nothing else.",
     [("regex_full", r"\[\[[^\[\]]+\]\]"), ("bracket_words", 5), ("title_case", None)]),
    ("Describe a cat in exactly 25 words. Do not use any commas.",
     [("word_count", 25), ("no_char", ",")]),
    ("Reply with a valid Python list of exactly 6 distinct prime numbers greater than 50, in ascending order, and nothing else.",
     [("pylist_primes", (6, 50))]),
    ("Write three bullet points ('- ') about rain. The first must contain exactly 4 words, the second exactly 6 words, the third exactly 8 words.",
     [("bullet_word_counts", [4, 6, 8])]),
    ("Spell the word 'strawberry' backwards in uppercase letters, then on a new line write how many letters 'r' it contains as a digit. Output exactly those two lines.",
     [("exact_lines", ["YRREBWARTS", "3"])]),
    ("Write a sentence that contains the words 'river', 'silver' and 'quiet' in that order, has between 10 and 15 words, and ends with a question mark.",
     [("ordered_words", ["river", "silver", "quiet"]), ("word_range", (10, 15)), ("endswith", "?")]),
    ("Output the numbers from 1 to 20, separated by commas without spaces, but replace multiples of 3 with 'X' and multiples of 7 with 'Y' (multiples of both: 'XY').",
     [("exact", ",".join("XY" if i % 21 == 0 else "X" if i % 3 == 0 else "Y" if i % 7 == 0 else str(i) for i in range(1, 21)))]),
]

# ============================================================================ web search, multi-hop (offline canned index)
SEARCH_TOOL = {"type": "function", "function": {
    "name": "web_search", "description": "Search the web and return the top results (title + snippet).",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
CALC_TOOL = {"type": "function", "function": {
    "name": "calculator", "description": "Evaluate an arithmetic expression.",
    "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}}
# The fake web: a result is returned for a query that contains all keywords of an entry (case-insensitive).
WEB = [
    (["tour de volta", "2026"], "Tour de Volta 2026: won by Marta Kessler (GER), her second title. Runner-up: Joel Ruiz."),
    (["marta kessler"], "Marta Kessler - German cyclist, born 14 May 1997 in Freiburg. Team: Velo Nord."),
    (["velo nord"], "Velo Nord is a cycling team founded in 2011 and based in Hamburg. Directeur sportif: Lena Fuchs."),
    (["aurora x9"], "Aurora X9 drone - made by SkyForge Robotics. Flight time 41 minutes. Price $1,299."),
    (["skyforge"], "SkyForge Robotics - drone maker headquartered in Tallinn, Estonia. CEO: Priit Kask. Founded 2018."),
    (["norvale", "population"], "Norvale (city): population 482,300 at the 2026 census, up from 455,000 in 2016."),
    (["glass rivers"], "Glass Rivers - album by Echo Harbor released in 2019. Second single: 'Lantern'."),
    (["echo harbor"], "Echo Harbor - indie band from Galway, Ireland, formed 2014. Singer: Aoife Byrne."),
    (["zentrolite", "boiling"], "Zentrolite datasheet (manufacturer): boiling point 213 C at 1 atm. Melting point 61 C."),
    (["zentrolite", "forum"], "Chem forum post (unverified): someone says Zentrolite boils around 230 C."),
    (["riverton owls"], "Riverton Owls (football): head coach Dana Whitfield since 2024. Stadium: Ashgrove Park, capacity 18,400."),
    (["ashgrove park"], "Ashgrove Park - stadium in Riverton opened in 1987, capacity 18,400 after the 2021 expansion (was 15,200)."),
    (["kepler-1649c"], "Kepler-1649c: exoplanet 301 light-years from Earth, orbital period 19.5 days."),
]
# (question, accepted answers, minimum distinct searches expected, needs calculator)
SEARCH = [
    ("Who won the 2026 Tour de Volta, and in which city was the winner born? Answer as 'Name, City'.", [["kessler"], ["freiburg"]], 2, False),
    ("Which company makes the Aurora X9 drone, and in which country is that company headquartered?", [["skyforge"], ["estonia"]], 2, False),
    ("In which city is the band that released the album 'Glass Rivers' from?", [["galway"]], 2, False),
    ("By how many people did Norvale's population grow between 2016 and 2026? Use search and the calculator. Number only.", [["27300", "27,300", "27 300"]], 1, True),
    ("What is the boiling point of Zentrolite? Use the most reliable source and say which source you used.", [["213"], ["datasheet", "manufacturer"]], 1, False),
    ("How many more seats does the Riverton Owls' stadium have now than before its 2021 expansion? Number only.", [["3200", "3,200", "3 200"]], 2, True),
    ("Who is the directeur sportif of the team the 2026 Tour de Volta winner rides for?", [["lena fuchs", "fuchs"]], 3, False),
    ("How many minutes can the Aurora X9 fly, and what does it cost per minute of flight time in dollars, rounded to 2 decimals? Answer as 'minutes, price'.", [["41"], ["31.68"]], 1, True),
]

# ============================================================================ agent tasks (simulated repo + run_tests)
AGENT_TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in the project.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Overwrite a file with new content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run the project's tests (python test_*.py files) and return the output.", "parameters": {"type": "object", "properties": {}}}},
]
AGENT = [
    ("The tests fail. Find and fix the bug(s) in the project so that run_tests passes. Do not modify test files.",
     {"stats.py": "def mean(xs):\n    return sum(xs) / len(xs) - 1\n\ndef median(xs):\n    s = sorted(xs)\n    n = len(s)\n    return s[n // 2]\n",
      "test_stats.py": "from stats import mean, median\nassert mean([1, 2, 3, 4]) == 2.5\nassert median([3, 1, 2]) == 2\nassert median([4, 1, 3, 2]) == 2.5\nprint('ok')\n"}, "tests_pass"),
    ("Add a function `slugify(title)` to text.py that lowercases, replaces runs of non-alphanumeric characters with a single '-' and strips leading/trailing '-'. Make run_tests pass without editing tests.",
     {"text.py": "def shout(s):\n    return s.upper() + '!'\n",
      "test_text.py": "from text import shout, slugify\nassert shout('hi') == 'HI!'\nassert slugify('Hello, World!') == 'hello-world'\nassert slugify('  --A  b--c ') == 'a-b-c'\nassert slugify('') == ''\nprint('ok')\n"}, "tests_pass"),
    ("Read sales.csv and write report.txt containing one line per region in alphabetical order, formatted 'Region: total' with the total of the amount column as an integer.",
     {"sales.csv": "region,amount\nNorth,120\nSouth,80\nNorth,30\nEast,55\nSouth,20\nEast,45\nWest,0\n"}, "report"),
    ("The function in parser.py is used by app.py. Rename it from parse_cfg to parse_config everywhere (all files) and make sure run_tests still passes.",
     {"parser.py": "def parse_cfg(text):\n    out = {}\n    for line in text.splitlines():\n        if '=' in line:\n            k, v = line.split('=', 1)\n            out[k.strip()] = v.strip()\n    return out\n",
      "app.py": "from parser import parse_cfg\n\ndef load(text):\n    return parse_cfg(text)\n",
      "test_app.py": "import parser, app\nassert not hasattr(parser, 'parse_cfg') and hasattr(parser, 'parse_config')\nassert app.load('a = 1\\nb=2') == {'a': '1', 'b': '2'}\nprint('ok')\n"}, "tests_pass"),
    ("config.json has a bug: the 'timeout' must be the sum of all values in 'retries_ms', and 'enabled' must be true. Fix config.json (keep it valid JSON with the same keys).",
     {"config.json": '{"name": "svc", "enabled": false, "retries_ms": [150, 300, 600, 1200], "timeout": 1000}'}, "config"),
    ("Implement the missing function `merge_sorted(a, b)` in lists.py (merge two sorted lists into one sorted list, in O(len(a)+len(b)), without calling sort/sorted) and make run_tests pass.",
     {"lists.py": "def merge_sorted(a, b):\n    raise NotImplementedError\n",
      "test_lists.py": "import lists, inspect\nfrom lists import merge_sorted\nassert merge_sorted([1, 4, 9], [2, 3, 10, 11]) == [1, 2, 3, 4, 9, 10, 11]\nassert merge_sorted([], [1]) == [1] and merge_sorted([], []) == []\nimport re\nsrc = inspect.getsource(lists)\nassert not re.search(r'(?<![\\w.])sorted\\(', src) and '.sort(' not in src\nprint('ok')\n"}, "tests_pass"),
]

# ============================================================================ vision (images drawn by make_images_hard.ps1)
VISION = [
    ("h_table_sum", "What is the total of the 'Q2' column in this table? Number only.", [["1167"]]),
    ("h_table_lookup", "In this table, which product had the highest Q3 value? Answer with the product name only.", [["delta"]]),
    ("h_chart_value", "Read this bar chart. What is the value of the 'Thu' bar? Number only.", [["37"]]),
    ("h_count_dots", "How many black dots are in this image? Number only.", [["17"]]),
    ("h_small_text", "Read the serial number printed in small text at the bottom right. Reply with the serial only.", [["SN-4471-XQ"]]),
    ("h_spatial", "Which shape is directly below the red circle: answer with the colour of that shape only.", [["yellow"]]),
    ("h_clock", "What time does this analog clock show? Answer as H:MM.", [["4:50"]]),
    ("h_receipt", "This is a receipt. What is the total after the 10% discount shown? Number only with 2 decimals.", [["38.70"]]),
]

# ============================================================================ long context (multi-needle, ~30k tokens)
LONGCTX = [
    {"needles": ["The vault code begins with the digits 47.", "The vault code ends with the digits 19.", "The middle digits of the vault code are 82."],
     "question": "What is the full six-digit vault code? Digits only.", "answer": ["478219"]},
    {"needles": ["Mira was born in 1991.", "Mira's brother Teo is 7 years younger than Mira.", "Teo's daughter was born when Teo was 29."],
     "question": "In which year was Teo's daughter born? Number only.", "answer": ["2027"]},
]

# ---------------------------------------------------------------------------- self-checks of the computed answers
assert sum(1 for i in range(1, 1001) if (i % 3 == 0 or i % 5 == 0) and i % 15) == 401
assert pow(7, 2026, 10) == 9
assert _dt.date(2000, 1, 1).strftime("%A").lower() == "saturday"
assert (_dt.date(2026, 11, 9) - _dt.date(2026, 3, 15)).days - 1 == 238
assert (_dt.date(2026, 10, 16) - _dt.date(2000, 1, 1)).days == 9785 and (_dt.date(2400, 2, 29) - _dt.date(1600, 3, 1)).days == 292193
assert 10 * 11 == 110 and round(10000 * 1.1 ** 3) == 13310 and 120 * 2 / (120 / 60 + 120 / 40) == 48
assert 482300 - 455000 == 27300 and 18400 - 15200 == 3200 and round(1299 / 41, 2) == 31.68
assert round(40 * 1.1, 2) == 44.0 and 50 - 44 == 6
assert [n for n in range(100, 1000) if sum(map(int, str(n))) == 13 and int(str(n)[0]) == 2 * int(str(n)[2]) and int(str(n)[1]) == int(str(n)[2]) + 1] == [643]
assert 51 + 53 + 55 == 159
