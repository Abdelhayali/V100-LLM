import os as _os, subprocess as _sp, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
def run_cli(args, timeout=60):
    return _sp.run([_sys.executable, "-X", "utf8", "-I", "-B", _os.path.join(_HERE, "_boot.py")] + list(args),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=_HERE)

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
    p = '\n'.join(p[i:i + 9] for i in range(0, 81, 9))
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
