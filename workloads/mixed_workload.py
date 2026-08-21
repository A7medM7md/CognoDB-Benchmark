"""
Sustained concurrent read/write throughput at a stated client concurrency.
Each 'client' is a thread issuing back-to-back ops for a fixed duration —
this mirrors real connection-pool concurrency more closely than raw
asyncio for driver comparisons, and keeps the code identical across
platforms since every adapter method is synchronous.
"""
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def _client_loop(adapter, node_ids, end_time, write_ratio, rnd_seed):
    rnd = random.Random(rnd_seed)
    ops = 0
    while time.perf_counter() < end_time:
        if rnd.random() < write_ratio:
            src, dst = rnd.choice(node_ids), rnd.choice(node_ids)
            adapter.mixed_write(src, dst)
        else:
            adapter.indexed_lookup(rnd.choice(node_ids))
        ops += 1
    return ops


def run_mixed_workload(adapter, node_ids, concurrency: int, duration_s: int = 15, write_ratio: float = 0.2):
    end_time = time.perf_counter() + duration_s
    total_ops = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(_client_loop, adapter, node_ids, end_time, write_ratio, seed)
            for seed in range(concurrency)
        ]
        for f in as_completed(futures):
            total_ops += f.result()

    return {
        "concurrency": concurrency,
        "duration_s": duration_s,
        "write_ratio": write_ratio,
        "total_ops": total_ops,
        "ops_per_sec": round(total_ops / duration_s, 2),
    }
