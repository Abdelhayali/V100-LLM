import os as _os, subprocess as _sp, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
def run_cli(args, timeout=60):
    return _sp.run([_sys.executable, "-X", "utf8", "-I", "-B", _os.path.join(_HERE, "_boot.py")] + list(args),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=_HERE)

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
    write('t1.csv', 'k,v\nb,5\na,5\nc,9\nd,1\n')
    d = json.loads(run(['t1.csv', '--group', 'k', '--sum', 'v', '--sort', 'total', '--top', '3'])[1])
    assert [g['key'] for g in d['groups']] == ['c', 'a', 'b']

def test_float_rounding():
    write('t2.csv', 'k,v\nx,0.1\nx,0.2\ny,1.005\ny,2\n')
    d = json.loads(run(['t2.csv', '--group', 'k', '--sum', 'v'])[1])
    g = {x['key']: x['total'] for x in d['groups']}
    assert g['x'] == 0.3 and isinstance(g['x'], float) and abs(g['y'] - 3.0) < 0.011

def test_int_when_whole():
    write('t3.csv', 'k,v\nx,1.5\nx,2.5\n')
    out = run(['t3.csv', '--group', 'k', '--sum', 'v'])[1]
    assert json.loads(out)['groups'][0]['total'] == 4 and '"total": 4,' in out.replace('4.0', 'X') or json.loads(out)['groups'][0]['total'] == 4 and type(json.loads(out)['groups'][0]['total']) is int

def test_missing_file():
    code, out, err = run(['nope.csv', '--group', 'k', '--sum', 'v'])
    assert code == 2 and err.strip()

def test_unknown_column():
    code, out, err = run(['sales.csv', '--group', 'zone', '--sum', 'amount'])
    assert code == 2 and err.strip()

def test_quoted_fields():
    write('t4.csv', 'name,amount\n"Smith, J",10\n"Smith, J",5\nLee,1\n')
    d = json.loads(run(['t4.csv', '--group', 'name', '--sum', 'amount'])[1])
    assert {'key': 'Smith, J', 'total': 15, 'rows': 2} in d['groups']

def test_main_function():
    import report
    assert report.main(['sales.csv', '--group', 'rep', '--sum', 'amount', '--top', '1']) == 0
