# Analysis

_Fill in after running `python -m harness.run_all` against your own
free-tier accounts. Structure below is the intended shape — replace the
bracketed prompts with real numbers and reasoning._

## Network baseline — read this first, apply it to every section below

From `results/RESULTS.md`'s network baseline table:

| Platform | Deployment | Baseline p50 |
|---|---|---|
| CognoDB | cloud | [fill in] ms |
| AuraDB | cloud | [fill in] ms |
| Memgraph | cloud | [fill in] ms |
| ArangoDB | self-hosted | ~0 ms |
| FalkorDB | self-hosted | ~0 ms |

**Every latency comparison below between a cloud platform and a
self-hosted one should subtract the cloud platform's baseline p50
first.** Example: if CognoDB's 1-hop p50 is 32ms and its network
baseline p50 is 24ms, its engine-level 1-hop cost is ~8ms — that's the
number to compare against ArangoDB's raw ~[X]ms, not the unadjusted 32ms.

## Ingest

Which platform loaded fastest, and does that track with its architecture
(in-memory vs disk-first, single round-trip UNWIND vs per-row inserts)?

## Traversals (1/2/3-hop)

Does latency growth per extra hop look linear or worse per platform? This
usually reveals whether a platform has real index-free adjacency (graph-
native storage) vs joins-under-the-hood (multi-model engines like Arango).

## Lookups

Indexed vs point-lookup gap per platform — a big gap means the index is
doing real work; a near-zero gap on some platform may mean point_lookup
silently used the index anyway (call this out, don't hide it).

## Mixed workload / concurrency

Where does throughput plateau or fall over as concurrency rises from 1 to
40 clients? On a 0.5 vCPU tier this is expected to happen early — say
where, and why (connection pool limits, CPU throttling, lock contention).

## Footprint

Whatever was actually observable per platform — compare stored size for
the same 120k/200k dataset.

## Overall

No single winner is expected by design (different engines, different
tiers). Summarize the actual trade-offs seen in the numbers above.
