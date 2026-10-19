import os as _os, subprocess as _sp, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
def run_cli(args, timeout=60):
    return _sp.run([_sys.executable, "-X", "utf8", "-I", "-B", _os.path.join(_HERE, "_boot.py")] + list(args),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=_HERE)

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
        f.write('the\ncat\n')
    r = run_cli(['-m', 'textstats', 'sample.txt', '--top', '1', '--stop', 'stop.txt'])
    assert r.stdout.splitlines()[-1] in ("café 1", "did 1", "don't 1")

def test_cli_missing():
    r = run_cli(['-m', 'textstats', 'missing.txt'])
    assert r.returncode == 1 and r.stderr.strip()
