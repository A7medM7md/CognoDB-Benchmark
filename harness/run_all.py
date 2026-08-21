"""
Single entrypoint: python -m harness.run_all [--only cognodb,aura]

Loads the identical dataset into each platform, runs every required
workload from the assignment (section 5.2), and writes one JSON file
per platform to results/raw/<platform>.json. report_generator.py then
turns those JSONs into the README results tables + charts.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loaders.platforms import get_platforms
from harness.network_baseline import main as run_network_baseline
from workloads.read_workloads import (
    run_traversal_workload,
    run_lookup_workload,
    run_aggregation_workload,
)
from workloads.mixed_workload import run_mixed_workload

DATASET_DIR = Path(__file__).parent.parent / "dataset"
RESULTS_DIR = Path(__file__).parent.parent / "results" / "raw"
READ_ITERATIONS = int(os.environ.get("READ_ITERATIONS", 100))
CONCURRENCY_LEVELS = [int(x) for x in os.environ.get("CONCURRENCY_LEVELS", "1,10,40").split(",")]


def load_dataset():
    nodes_path = DATASET_DIR / "pokec_nodes.csv"
    edges_path = DATASET_DIR / "pokec_sample.csv"
    if not nodes_path.exists() or not edges_path.exists():
        sys.exit("Dataset not found — run `python dataset/download_dataset.py` first.")

    with open(nodes_path) as f:
        node_ids = [row["node_id"] for row in csv.DictReader(f)]
    with open(edges_path) as f:
        edges = [(row["src"], row["dst"]) for row in csv.DictReader(f)]
    return node_ids, edges


def benchmark_platform(key, adapter, node_ids, edges):
    print(f"\n=== {adapter.name} ({adapter.query_language}) ===")
    result = {
        "platform": adapter.name,
        "query_language": adapter.query_language,
        "dataset": {"nodes": len(node_ids), "edges": len(edges)},
    }

    print("  connecting...")
    adapter.connect()

    try:
        print("  clearing existing data...")
        adapter.clear()

        print("  loading nodes...")
        node_load_s = adapter.load_nodes(node_ids)
        print("  loading edges...")
        edge_load_s = adapter.load_edges(edges)
        print("  creating indexes...")
        adapter.create_indexes()

        result["ingest"] = {
            "node_load_seconds": round(node_load_s, 3),
            "edge_load_seconds": round(edge_load_s, 3),
            "nodes_per_sec": round(len(node_ids) / node_load_s, 1) if node_load_s else None,
            "rels_per_sec": round(len(edges) / edge_load_s, 1) if edge_load_s else None,
        }

        print("  traversal workloads (1/2/3-hop)...")
        result["traversals"] = {
            f"{h}_hop": run_traversal_workload(adapter, node_ids, h, READ_ITERATIONS)
            for h in (1, 2, 3)
        }

        print("  lookup workloads...")
        result["lookups"] = {
            "indexed": run_lookup_workload(adapter, node_ids, indexed=True, iterations=READ_ITERATIONS),
            "point": run_lookup_workload(adapter, node_ids, indexed=False, iterations=READ_ITERATIONS),
        }

        print("  aggregation workload...")
        result["aggregation"] = run_aggregation_workload(adapter)

        print("  mixed read/write workload (concurrency sweep)...")
        result["mixed_workload"] = [
            run_mixed_workload(adapter, node_ids, concurrency=c)
            for c in CONCURRENCY_LEVELS
        ]

        print("  footprint...")
        result["footprint"] = adapter.footprint()

    finally:
        adapter.close()

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated platform keys, e.g. cognodb,aura")
    args = parser.parse_args()

    node_ids, edges = load_dataset()
    print(f"Dataset loaded into memory: {len(node_ids):,} nodes / {len(edges):,} edges")

    print("\n=== Network baseline (fairness instrument, see harness/network_baseline.py) ===")
    run_network_baseline()

    platforms = get_platforms()
    keys = args.only.split(",") if args.only else list(platforms.keys())

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for key in keys:
        adapter = platforms[key]
        try:
            result = benchmark_platform(key, adapter, node_ids, edges)
            result["status"] = "ok"
        except Exception as e:
            print(f"  !! FAILED: {e}")
            result = {"platform": key, "status": "failed", "error": str(e)}

        out_path = RESULTS_DIR / f"{key}.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  -> wrote {out_path}")


if __name__ == "__main__":
    main()
