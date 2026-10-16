"""V100-LLM evaluation tasks. Every task is graded automatically (no LLM judge), offline and deterministic."""

# ----------------------------------------------------------------------------- coding
# The model writes the function; hidden tests run it in a separate Python process.
CODING = [
    ("is_prime", "Write a Python function `is_prime(n: int) -> bool` that returns True if n is a prime number.",
     "assert is_prime(2) and is_prime(97) and is_prime(7919)\nassert not is_prime(1) and not is_prime(0) and not is_prime(-7) and not is_prime(91) and not is_prime(4)"),
    ("fizzbuzz", "Write `fizzbuzz(n: int) -> list[str]` returning the FizzBuzz strings for 1..n ('Fizz' for multiples of 3, 'Buzz' for 5, 'FizzBuzz' for both, else the number as a string).",
     "assert fizzbuzz(15)[-1] == 'FizzBuzz' and fizzbuzz(5) == ['1','2','Fizz','4','Buzz'] and len(fizzbuzz(100)) == 100"),
    ("roman", "Write `to_roman(n: int) -> str` converting 1..3999 to a Roman numeral.",
     "assert to_roman(1994) == 'MCMXCIV' and to_roman(3999) == 'MMMCMXCIX' and to_roman(4) == 'IV' and to_roman(58) == 'LVIII'"),
    ("anagrams", "Write `group_anagrams(words: list[str]) -> list[list[str]]` grouping words that are anagrams; order inside groups follows input order, groups ordered by first appearance.",
     "assert group_anagrams(['eat','tea','tan','ate','nat','bat']) == [['eat','tea','ate'],['tan','nat'],['bat']]\nassert group_anagrams([]) == []"),
    ("balanced", "Write `balanced(s: str) -> bool` that checks whether the brackets ()[]{} in s are balanced (other characters are ignored).",
     "assert balanced('a(b[c]{d}e)f') and balanced('') and not balanced('(]') and not balanced('((') and not balanced('}{')"),
    ("lru", "Write a class `LRUCache` with `__init__(self, capacity: int)`, `get(self, key) -> int` (returns -1 if missing) and `put(self, key, value)`, evicting the least recently used item when full.",
     "c = LRUCache(2); c.put(1,1); c.put(2,2); assert c.get(1) == 1; c.put(3,3); assert c.get(2) == -1; c.put(4,4); assert c.get(1) == -1 and c.get(3) == 3 and c.get(4) == 4"),
    ("merge_intervals", "Write `merge_intervals(iv: list[list[int]]) -> list[list[int]]` merging overlapping intervals, sorted by start.",
     "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]] and merge_intervals([[1,4],[4,5]]) == [[1,5]] and merge_intervals([]) == []"),
    ("word_freq", "Write `top_words(text: str, k: int) -> list[tuple[str, int]]` returning the k most common words (lower-cased, letters only, split on non-letters), ties broken alphabetically.",
     "assert top_words('The cat and the hat. The CAT!', 2) == [('the', 3), ('cat', 2)]\nassert top_words('b a c a b a', 3) == [('a', 3), ('b', 2), ('c', 1)]"),
    ("binary_search", "Write `search_insert(nums: list[int], target: int) -> int` returning the index of target in sorted nums, or where it would be inserted. Must be O(log n).",
     "assert search_insert([1,3,5,6],5) == 2 and search_insert([1,3,5,6],2) == 1 and search_insert([1,3,5,6],7) == 4 and search_insert([],3) == 0"),
    ("matrix_spiral", "Write `spiral(m: list[list[int]]) -> list[int]` returning the elements of matrix m in clockwise spiral order.",
     "assert spiral([[1,2,3],[4,5,6],[7,8,9]]) == [1,2,3,6,9,8,7,4,5] and spiral([[1,2,3,4],[5,6,7,8],[9,10,11,12]]) == [1,2,3,4,8,12,11,10,9,5,6,7] and spiral([]) == []"),
    ("csv_avg", "Write `column_average(csv_text: str, column: str) -> float` that parses CSV text with a header row and returns the average of the numeric values in `column`, skipping empty or non-numeric cells. Raise ValueError if the column does not exist.",
     "t = 'name,score\\na,10\\nb,\\nc,x\\nd,20\\n'\nassert abs(column_average(t, 'score') - 15.0) < 1e-9\ntry:\n    column_average(t, 'nope'); raise AssertionError('no error')\nexcept ValueError:\n    pass"),
    ("dijkstra", "Write `shortest_path(graph: dict, start, end) -> int` returning the length of the shortest path in a weighted directed graph given as {node: {neighbour: weight}}; return -1 if unreachable.",
     "g = {'a': {'b': 1, 'c': 4}, 'b': {'c': 2, 'd': 5}, 'c': {'d': 1}, 'd': {}}\nassert shortest_path(g, 'a', 'd') == 4 and shortest_path(g, 'd', 'a') == -1 and shortest_path(g, 'a', 'a') == 0"),
]

# ----------------------------------------------------------------------------- chat / reasoning
# (question, list of accepted answers - matched as whole words in the reply, case-insensitive)
CHAT = [
    ("A shop sells pens at 3 for $2. How many dollars do 27 pens cost? Answer with the number only.", ["18"]),
    ("What is 17 * 23? Answer with the number only.", ["391"]),
    ("If today is Wednesday, what day of the week will it be 100 days from now? Answer with the day only.", ["friday"]),
    ("A train leaves at 09:40 and the trip takes 2 hours 35 minutes. At what time (HH:MM, 24-hour) does it arrive?", ["12:15"]),
    ("What is the chemical symbol for tungsten?", ["w"]),
    ("Which planet in our solar system has the most moons as of 2024: Jupiter or Saturn?", ["saturn"]),
    ("Alice is older than Bob. Bob is older than Carol. Who is the youngest? Answer with the name only.", ["carol"]),
    ("I have 3 apples. I eat one, buy five more, then give away half of what I have. How many apples do I have? Number only.", ["3.5", "3½", "3 1/2", "three and a half"]),
    ("What is the capital of Australia? One word.", ["canberra"]),
    ("Sort these numbers ascending and give only the middle one: 42, 7, 19, 88, 3.", ["19"]),
    ("A rectangle has a perimeter of 30 cm and its length is twice its width. What is its area in square cm? Number only.", ["50"]),
    ("How many prime numbers are there between 1 and 30? Number only.", ["10"]),
]

# ----------------------------------------------------------------------------- instruction following
# (prompt, checker name, argument) - checkers live in run_eval.py
IFEVAL = [
    ("Describe the moon in fewer than 40 words.", "max_words", 40),
    ("List three fruits as a JSON array of strings and output nothing else.", "json_list_len", 3),
    ("Write one sentence about rain without using any commas.", "no_char", ","),
    ("Reply with the word OK in all capital letters and nothing else.", "exact", "OK"),
    ("Write exactly three bullet points (lines starting with '- ') about exercise.", "bullets", 3),
    ("Write a short greeting that ends with the exact phrase 'See you soon.'", "endswith", "See you soon."),
    ("Answer in lowercase letters only: what is the largest ocean?", "lowercase_contains", "pacific"),
    ("Give a title for a story about a lost dog, wrapped in double angular brackets like <<title>>.", "regex", r"<<[^<>]+>>"),
]

# ----------------------------------------------------------------------------- web search (tool use)
SEARCH_TOOL = {"type": "function", "function": {
    "name": "web_search", "description": "Search the web and return the top results (title + snippet).",
    "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "search query"}},
                   "required": ["query"]}}}
# (question, keywords the query must contain (any), canned search results, accepted final answers)
SEARCH = [
    ("Use web search: who won the 2026 Tour de Volta cycling race?", ["tour de volta"],
     "1. Tour de Volta 2026 results - Marta Kessler (GER) won the 2026 Tour de Volta ahead of J. Ruiz.\n2. Kessler takes second Volta title.", ["kessler"]),
    ("Search the web for the current population of the fictional city of Norvale and tell me the number.", ["norvale"],
     "1. Norvale city facts: population 482,300 (2026 census).\n2. Norvale tourism board.", ["482,300", "482300", "482 300"]),
    ("What is the boiling point of the compound Zentrolite according to a web search? Answer with the temperature.", ["zentrolite"],
     "1. Zentrolite datasheet: melting point 61 C, boiling point 213 C.\n2. Zentrolite safety notes.", ["213"]),
    ("Look up online which company makes the Aurora X9 drone.", ["aurora x9"],
     "1. Aurora X9 review - the X9 is made by SkyForge Robotics.\n2. SkyForge announces X10.", ["skyforge"]),
    ("Find the release year of the album 'Glass Rivers' by the band Echo Harbor using web search.", ["glass rivers"],
     "1. Echo Harbor - Glass Rivers (2019) album page.\n2. Echo Harbor discography.", ["2019"]),
    ("Use the search tool to find who is the head coach of the Riverton Owls football team.", ["riverton owls"],
     "1. Riverton Owls staff - head coach: Dana Whitfield (since 2024).\n2. Owls schedule.", ["whitfield"]),
]

# ----------------------------------------------------------------------------- agent tasks (multi-step tool loops)
AGENT_TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files in the project.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Overwrite a file with new content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "calculator", "description": "Evaluate an arithmetic expression.", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {"name": "add_event", "description": "Add a calendar event.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"}, "time": {"type": "string", "description": "HH:MM"}}, "required": ["title", "date", "time"]}}},
]
# (instruction, initial files, checker name) - checkers in run_eval.py
AGENT = [
    ("There is a bug in utils.py: the function add returns the wrong result. Find it with the tools and fix the file.",
     {"utils.py": "def add(a, b):\n    return a - b\n", "README.md": "Utility functions."}, "fix_add"),
    ("Read config.ini and change the port setting to 9090, keeping everything else unchanged.",
     {"config.ini": "[server]\nhost = 127.0.0.1\nport = 8080\ndebug = false\n"}, "port_9090"),
    ("Use the calculator to compute (1234 * 5678) - 999 and write only the result into result.txt.",
     {}, "calc_result"),
    ("Schedule a meeting titled 'Design review' on 2026-11-03 at 14:30 using the calendar tool.",
     {}, "event"),
    ("Find which file in the project mentions 'TODO' and write its file name into todo.txt.",
     {"a.py": "print('hello')\n", "b.py": "# TODO: handle errors\nx = 1\n", "c.md": "Notes."}, "todo_file"),
]

# ----------------------------------------------------------------------------- vision (images generated by run_eval.py)
VISION = [
    ("shapes", "How many shapes are in this image, and what colour is the triangle? Answer as: <number>, <colour>.", [["3", "three"], ["green"]]),
    ("text", "What is the exact code written in this image? Reply with the code only.", [["K7-9QX"]]),
    ("chart", "This bar chart shows sales per quarter. Which quarter (Q1-Q4) has the highest bar? Answer with the quarter only.", [["q3"]]),
    ("table", "In this table, what is Bob's age? Number only.", [["41"]]),
]
