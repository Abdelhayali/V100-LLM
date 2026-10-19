import os as _os, subprocess as _sp, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
def run_cli(args, timeout=60):
    return _sp.run([_sys.executable, "-X", "utf8", "-I", "-B", _os.path.join(_HERE, "_boot.py")] + list(args),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=_HERE)

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
    assert not re.search(r'(?<![\w.])(eval|exec|compile)\s*\(', src) and not re.search(r'^\s*(import|from)\s+ast\b', src, re.M)
