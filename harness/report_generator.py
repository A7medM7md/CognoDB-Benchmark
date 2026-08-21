"""
python -m harness.report_generator

Reads every results/raw/<platform>.json and writes:
  results/RESULTS.md         (markdown tables, paste into README)
  results/charts/*.png       (p50/p95 bar charts per workload)
"""
import json
from pathlib import Path
from tabulate import tabulate
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW_DIR = Path(__file__).parent.parent / "results" / "raw"
CHARTS_DIR = Path(__file__).parent.parent / "results" / "charts"
OUT_MD = Path(__file__).parent.parent / "results" / "RESULTS.md"


def load_results():
    results = {}
    for f in sorted(RAW_DIR.glob("*.json")):
        if f.stem == "network_baseline":
            continue
        with open(f) as fh:
            results[f.stem] = json.load(fh)
    return results


def load_network_baseline():
    path = RAW_DIR / "network_baseline.json"
    if not path.exists():
        return None
    with open(path) as fh:
        return json.load(fh)


def build_network_baseline_table(baseline):
    rows = []
    for key, r in baseline.items():
        if "round_trip_ms" not in r:
            rows.append([r.get("platform", key), "-", "FAILED", "-"])
            continue
        rt = r["round_trip_ms"]
        rows.append([r["platform"], r["deployment"], rt["p50"], rt["p95"]])
    return tabulate(rows, headers=["Platform", "Deployment", "Baseline p50 (ms)", "Baseline p95 (ms)"], tablefmt="github")


def build_ingest_table(results):
    rows = []
    for key, r in results.items():
        if r.get("status") != "ok":
            rows.append([r.get("platform", key), "FAILED", "-", "-", "-"])
            continue
        ing = r["ingest"]
        rows.append([
            r["platform"], r["query_language"],
            f"{ing['nodes_per_sec']:.0f}" if ing["nodes_per_sec"] else "-",
            f"{ing['rels_per_sec']:.0f}" if ing["rels_per_sec"] else "-",
            f"{ing['node_load_seconds'] + ing['edge_load_seconds']:.1f}s",
        ])
    return tabulate(rows, headers=["Platform", "Query Lang", "Nodes/sec", "Rels/sec", "Total load time"], tablefmt="github")


def build_latency_table(results, section, subsection):
    rows = []
    for key, r in results.items():
        if r.get("status") != "ok":
            continue
        m = r[section][subsection]
        rows.append([r["platform"], m["p50"], m["p95"], m["n"]])
    return tabulate(rows, headers=["Platform", "p50 (ms)", "p95 (ms)", "iterations"], tablefmt="github")


def build_mixed_table(results):
    rows = []
    for key, r in results.items():
        if r.get("status") != "ok":
            continue
        for run in r["mixed_workload"]:
            rows.append([r["platform"], run["concurrency"], run["write_ratio"], run["ops_per_sec"]])
    return tabulate(rows, headers=["Platform", "Concurrency", "Write ratio", "Ops/sec"], tablefmt="github")


def chart_latency(results, section, subsection, title, filename):
    platforms, p50s, p95s = [], [], []
    for key, r in results.items():
        if r.get("status") != "ok":
            continue
        m = r[section][subsection]
        platforms.append(r["platform"])
        p50s.append(m["p50"])
        p95s.append(m["p95"])

    if not platforms:
        return
    x = range(len(platforms))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([i - 0.2 for i in x], p50s, width=0.4, label="p50")
    ax.bar([i + 0.2 for i in x], p95s, width=0.4, label="p95")
    ax.set_xticks(list(x))
    ax.set_xticklabels(platforms, rotation=20, ha="right")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHARTS_DIR / filename, dpi=120)
    plt.close(fig)


def main():
    results = load_results()
    if not results:
        print("No results found in results/raw/ — run harness.run_all first.")
        return

    sections = []

    baseline = load_network_baseline()
    if baseline:
        sections.append(
            "## ⚠️ Network Baseline (read this before the tables below)\n\n"
            "Self-hosted platforms (ArangoDB, FalkorDB) run on the same machine "
            "as the benchmark client — their network round-trip is ~0ms by "
            "construction. Cloud platforms (CognoDB, AuraDB, Memgraph) pay a "
            "real public-internet round trip on every single query. This table "
            "isolates that cost using a trivial no-op query (`RETURN 1`, 50 "
            "iterations, no data touched) so every other latency number in this "
            "report can be read net of network overhead. **When comparing a "
            "self-hosted platform's latency to a cloud platform's, subtract the "
            "cloud platform's baseline p50 first** — otherwise you are "
            "partly comparing network topology, not database engines.\n\n"
            + build_network_baseline_table(baseline)
        )

    sections.append("## Data Loading\n\n" + build_ingest_table(results))

    for hop in (1, 2, 3):
        sections.append(f"## {hop}-hop Traversal Latency\n\n" +
                         build_latency_table(results, "traversals", f"{hop}_hop"))
        chart_latency(results, "traversals", f"{hop}_hop", f"{hop}-hop traversal latency", f"traversal_{hop}hop.png")

    sections.append("## Indexed Lookup Latency\n\n" + build_latency_table(results, "lookups", "indexed"))
    chart_latency(results, "lookups", "indexed", "Indexed lookup latency", "lookup_indexed.png")

    sections.append("## Aggregation Latency\n\n" +
                     tabulate(
                         [[r["platform"], r["aggregation"]["p50"], r["aggregation"]["p95"]]
                          for r in results.values() if r.get("status") == "ok"],
                         headers=["Platform", "p50 (ms)", "p95 (ms)"], tablefmt="github"))

    sections.append("## Mixed Read/Write Throughput\n\n" + build_mixed_table(results))

    OUT_MD.write_text("\n\n".join(sections) + "\n")
    print(f"Wrote {OUT_MD}")
    print(f"Charts in {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
