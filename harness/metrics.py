import time
import numpy as np


def timed_run(fn, *args, **kwargs):
    """Runs fn once, returns (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return result, elapsed_ms


def percentiles(latencies_ms: list[float]) -> dict:
    arr = np.array(latencies_ms)
    return {
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "min": round(float(arr.min()), 3),
        "max": round(float(arr.max()), 3),
        "n": len(arr),
    }


def warm_up(fn, args_list, rounds=10):
    """Runs fn against the first `rounds` argument tuples, discarding timings.
    Every workload calls this before it starts measuring."""
    for args in args_list[:rounds]:
        fn(*args)
