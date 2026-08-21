"""
Fairness instrument: measures the network round-trip cost in isolation,
separately from every other workload.

Why this exists: three platforms (CognoDB, AuraDB, Memgraph) are reached
over the public internet; two (ArangoDB, FalkorDB) are self-hosted on the
same machine as the client, so their measured latency is ~0ms of network
hop by construction. That's a real, unavoidable asymmetry in this
benchmark (see README "Known Fairness Limitation"). Rather than just
stating that in prose, this script quantifies it: a trivial query
(no data touched, no computation) run 50x per platform gives a baseline
"round-trip floor" that is dominated by network + protocol overhead
rather than the database engine. Every other latency number in this
benchmark should be read against this floor — e.g. if CognoDB's baseline
is 25ms and its 1-hop traversal p50 is 30ms, the traversal itself is only
costing ~5ms; the other ~25ms is unavoidable network cost that a
self-hosted platform never pays.

Run standalone: python -m harness.network_baseline
Also called automatically as the first step of harness/run_all.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness.metrics import timed_run, percentiles, warm_up
from loaders.platforms import get_platforms

ITERATIONS = 50
RESULTS_DIR = Path(__file__).parent.parent / "results" / "raw"


def noop_query(adapter):
    """Cheapest possible round trip: ask the DB for a constant, touch no data.
    Every adapter can answer this via aggregate_count_by_label on an empty
    graph, but that still touches the label index — instead we use the
    driver's own connectivity check where available, falling back to the
    lightest real query per platform."""
    if hasattr(adapter, "_driver") and adapter._driver:
        with adapter._driver.session() as s:
            s.run("RETURN 1").consume()
    elif hasattr(adapter, "_graph") and adapter._graph:
        adapter._graph.query("RETURN 1")
    elif hasattr(adapter, "_db") and adapter._db:
        list(adapter._db.aql.execute("RETURN 1"))
    else:
        raise RuntimeError("adapter has no recognizable connection handle")


def measure_baseline(key, adapter):
    print(f"  measuring network baseline for {adapter.name}...")
    adapter.connect()
    try:
        warm_up(lambda: noop_query(adapter), [() for _ in range(5)], rounds=5)
        latencies = []
        for _ in range(ITERATIONS):
            _, ms = timed_run(noop_query, adapter)
            latencies.append(ms)
        return percentiles(latencies)
    finally:
        adapter.close()


def main():
    platforms = get_platforms()
    baseline = {}
    for key, adapter in platforms.items():
        try:
            baseline[key] = {
                "platform": adapter.name,
                "deployment": "cloud (public internet)" if key in ("cognodb", "aura") else "self-hosted (same machine as client)",
                "round_trip_ms": measure_baseline(key, adapter),
            }
        except Exception as e:
            baseline[key] = {"platform": adapter.name, "status": "failed", "error": str(e)}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "network_baseline.json"
    with open(out_path, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"\nWrote {out_path}")

    print("\nRound-trip floor (p50 / p95, ms):")
    for key, r in baseline.items():
        if "round_trip_ms" in r:
            print(f"  {r['platform']:35s} [{r['deployment']}]  p50={r['round_trip_ms']['p50']}  p95={r['round_trip_ms']['p95']}")

    return baseline


if __name__ == "__main__":
    main()
