import os, runpy, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
args = sys.argv[1:]
if args and args[0] == "-m":
    sys.argv = [args[1]] + args[2:]
    runpy.run_module(args[1], run_name="__main__", alter_sys=True)
elif args and args[0] == "-c":
    sys.argv = ["-c"] + args[2:]
    exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__"})
else:
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")
