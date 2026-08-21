import random
from harness.metrics import timed_run, percentiles, warm_up


def pick_start_nodes(node_ids: list[str], n: int, seed: int = 7) -> list[str]:
    rnd = random.Random(seed)
    return rnd.sample(node_ids, min(n, len(node_ids)))


def run_traversal_workload(adapter, node_ids, hops: int, iterations: int = 100):
    starts = pick_start_nodes(node_ids, iterations + 10)
    warm_up(lambda nid: adapter.traverse(nid, hops), [(s,) for s in starts], rounds=10)

    latencies = []
    for nid in starts[10:10 + iterations]:
        _, ms = timed_run(adapter.traverse, nid, hops)
        latencies.append(ms)
    return percentiles(latencies)


def run_lookup_workload(adapter, node_ids, indexed: bool, iterations: int = 100):
    fn = adapter.indexed_lookup if indexed else adapter.point_lookup
    ids = pick_start_nodes(node_ids, iterations + 10, seed=13)
    warm_up(fn, [(i,) for i in ids], rounds=10)

    latencies = []
    for nid in ids[10:10 + iterations]:
        _, ms = timed_run(fn, nid)
        latencies.append(ms)
    return percentiles(latencies)


def run_aggregation_workload(adapter, iterations: int = 20):
    # aggregations are heavier — fewer iterations is standard practice,
    # noted explicitly here rather than silently reusing 100
    warm_up(lambda: adapter.aggregate_count_by_label(), [() for _ in range(3)], rounds=3)
    latencies = []
    for _ in range(iterations):
        _, ms = timed_run(adapter.aggregate_count_by_label)
        latencies.append(ms)
    return percentiles(latencies)
