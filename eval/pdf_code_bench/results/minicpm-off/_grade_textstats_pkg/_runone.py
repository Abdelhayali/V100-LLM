import os, sys, traceback
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
os.chdir(here)
import _hidden
try:
    getattr(_hidden, sys.argv[1])()
except BaseException as e:
    tb = traceback.extract_tb(e.__traceback__)
    print(f"{type(e).__name__}: {str(e)[:200]} (line {tb[-1].lineno if tb else '?'})")
    sys.exit(1)
