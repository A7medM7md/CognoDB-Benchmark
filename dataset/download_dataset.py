"""
Downloads and prepares the benchmark dataset.

Dataset: SNAP soc-Pokec social network (directed friendship graph).
Source:  https://snap.stanford.edu/data/soc-Pokec.html
Full graph: 1,632,803 nodes / 30,622,564 edges.

We take a deterministic subgraph (induced by the first N edges after a
seeded shuffle of the edge list) sized to comfortably fit inside every
platform's smallest free tier (CognoDB free tier: 256MB RAM / 1GB disk).
Target: ~120,000 relationships by default (see .env DATASET_REL_LIMIT),
node count follows automatically from however many distinct nodes touch
that many sampled edges.

Output: dataset/pokec_sample.csv  (columns: src,dst)
        dataset/pokec_nodes.csv   (column: node_id)

This keeps loading logic identical across every platform: each loader
reads these two CSVs and inserts the same nodes/edges the same way
(batched, same batch size), so load-time comparisons are apples-to-apples.
"""
import csv
import gzip
import os
import random
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

SNAP_URL = "https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz"
RAW_PATH = Path(__file__).parent / "soc-pokec-relationships.txt.gz"
EDGES_OUT = Path(__file__).parent / "pokec_sample.csv"
NODES_OUT = Path(__file__).parent / "pokec_nodes.csv"

REL_LIMIT = int(os.environ.get("DATASET_REL_LIMIT", 200_000))
SEED = 42


def download():
    if RAW_PATH.exists():
        print(f"[skip] {RAW_PATH} already downloaded")
        return
    print(f"Downloading {SNAP_URL} ...")
    urllib.request.urlretrieve(SNAP_URL, RAW_PATH)
    print(f"Saved to {RAW_PATH}")


def build_sample():
    random.seed(SEED)
    edges = []
    print("Reading full edge list (streaming, gzip)...")
    with gzip.open(RAW_PATH, "rt") as f:
        for line in f:
            src, dst = line.strip().split("\t")
            edges.append((src, dst))

    print(f"Full graph: {len(edges):,} directed edges")
    random.shuffle(edges)
    sample = edges[:REL_LIMIT]

    node_ids = set()
    for src, dst in sample:
        node_ids.add(src)
        node_ids.add(dst)

    print(f"Sample: {len(sample):,} edges / {len(node_ids):,} nodes")

    with open(EDGES_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst"])
        w.writerows(sample)

    with open(NODES_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id"])
        for n in sorted(node_ids, key=int):
            w.writerow([n])

    print(f"Wrote {EDGES_OUT} and {NODES_OUT}")


if __name__ == "__main__":
    download()
    build_sample()
    print("\nDone. Load this identical pair of CSVs into every platform.")
