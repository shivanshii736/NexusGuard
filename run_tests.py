import sys, traceback, tests.test_engine as t
fails = 0
for n in sorted(x for x in dir(t) if x.startswith("test_")):
    try:
        getattr(t, n)(); print("PASS", n)
    except Exception:
        fails += 1; print("FAIL", n); traceback.print_exc()
sys.exit(1 if fails else 0)
