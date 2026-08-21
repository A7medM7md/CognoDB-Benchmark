# CognoDB Cloud Benchmark

A reproducible, honest benchmark comparing **CognoDB Cloud** against four
other managed/self-hosted graph database platforms on identical hardware
tiers, identical data, and identical query workloads.

> Built for the Wexa AI take-home assignment. Every number in
> `results/RESULTS.md` comes from an automated run of this repo — nothing
> here is hand-typed or estimated.

## TL;DR — one-command run

```bash
git clone <this-repo>
cd cognodb-benchmark
cp .env.example .env        # fill in your own free-tier credentials
pip install -r requirements.txt
docker compose up -d        # starts ArangoDB + FalkorDB, capped to 0.5vCPU/256MB
python dataset/download_dataset.py
python -m harness.run_all
python -m harness.report_generator
```

Results land in `results/RESULTS.md` and `results/charts/*.png`.

## Platforms compared, and why

| Platform | Why it's in this comparison |
|---|---|
| **CognoDB Cloud** | subject of the benchmark |
| **Neo4j AuraDB Free** | CognoDB speaks the Bolt protocol and is queried with the official Neo4j driver — AuraDB is the most direct apples-to-apples comparison: same protocol, same query language, same driver, different backend engine |
| **Memgraph** (self-hosted, capped) | Bolt/Cypher-compatible in-memory-first engine — good contrast for traversal latency specifically. Originally targeted at Memgraph Cloud, but its free-tier connection endpoint only exposed a raw IP (no DNS hostname), which breaks TLS hostname verification by design — see `docs/CHANGES.md`. Moved to self-hosted, which also gives an exact 0.5vCPU/256MB cap instead of relying on the cloud trial's advertised specs. |
| **ArangoDB** (self-hosted, capped) | different query language (AQL) and a multi-model engine rather than graph-native — tests whether "graph-native" actually wins on this workload |
| **FalkorDB** (self-hosted, capped) | Redis-based graph engine, sparse footprint by design — interesting resource-efficiency comparison at these tiny tier sizes |

Two of the five (CognoDB, AuraDB) share the exact same adapter code
(`loaders/bolt_adapter.py`) because they're both Bolt+Cypher over TLS —
that removes "we phrased the query slightly differently" as a confound
between those two. Memgraph now also uses that same adapter class (same
Bolt+Cypher protocol) but self-hosted without TLS/auth — see the fairness
note below on why. ArangoDB and FalkorDB use different query languages
(AQL and Cypher-dialect respectively); the queries are logically
equivalent but not byte-identical — noted as a caveat, not hidden.

## Fairness / resource parity

| Platform | vCPU | RAM | Storage | Tier | Region |
|---|---|---|---|---|---|
| CognoDB Cloud | 0.5 (burstable) | 256 MB | 1 GB | free (c0) | us-east4 (N. Virginia) |
| Neo4j AuraDB Free | 0.5 (shared) | ~1 GB* | 1 GB | free | us-east1 (South Carolina) |
| Memgraph | 0.5 (docker-capped) | 256 MB (docker-capped) | local disk | self-hosted | n/a — runs on the client machine |
| ArangoDB | 0.5 (docker-capped) | 256 MB (docker-capped) | local disk | self-hosted | n/a — runs on the client machine |
| FalkorDB | 0.5 (docker-capped) | 256 MB (docker-capped) | local disk | self-hosted | n/a — runs on the client machine |

*AuraDB Free's published RAM allocation is fixed by Neo4j and isn't
independently adjustable — recorded here as a caveat, not concealed.
Dataset size (~120k nodes / 200k edges) was chosen specifically to fit
inside the smallest tier (CognoDB's 256MB) with headroom.

**Why Memgraph moved from cloud to self-hosted:** Memgraph Cloud's free
tier exposed only a raw IP address as the connection endpoint, not a DNS
hostname. TLS certificate hostname verification cannot succeed against a
bare IP by design (the cert is issued for a domain name), so every
connection attempt failed at the TLS layer regardless of credentials.
Self-hosting via `docker-compose.yml`, capped to the same 0.5vCPU/256MB
as every other self-hosted platform, sidesteps that entirely and — as a
side benefit — gives an exact, guaranteed resource cap instead of relying
on a cloud trial's advertised (and not independently verifiable) specs.

**Region choice rationale:** the two remaining cloud platforms are pinned
to the US East Coast (Virginia / South Carolina) to keep network latency
comparable between them — choosing geographically distant regions (e.g.
Frankfurt for one, Virginia for the other) would make network distance a
confounding variable indistinguishable from real engine latency
differences. The three self-hosted platforms have zero network hop by
construction (same machine as the client) — this is the single largest
apples-to-oranges factor in this benchmark and is called out again in
`docs/ANALYSIS.md` when interpreting their latency numbers.

## Dataset

[SNAP soc-Pokec](https://snap.stanford.edu/data/soc-Pokec.html) social
network, deterministic seeded sample (see `dataset/download_dataset.py`):
~120,000 nodes / 200,000 directed relationships. Same two CSVs loaded into
every platform with the same batch size (1,000 rows/batch).

## Methodology

- **Warm-up**: every read workload runs 10 warm-up calls (discarded) before
  the 100 measured iterations.
- **Percentiles, not just averages**: p50 and p95 reported for every
  latency metric.
- **Mixed workload**: 15-second sustained run per concurrency level
  (1 / 10 / 40 clients), 80/20 read/write mix, thread-pool clients.
- **Indexes**: every platform gets exactly one index — on `Person.node_id`
  — created after bulk load (faster than indexing during insert on every
  platform tested).
- **Automation**: `harness/run_all.py` is the single entrypoint; nothing
  in the results is manually run or manually timed.

## ⚠️ Known Fairness Limitation: Network Topology (read this first)

This is the single biggest apples-to-oranges factor in this benchmark,
and it's called out here deliberately rather than buried in a footnote.

Two platforms — **CognoDB, AuraDB** — are managed cloud services reached
over the public internet: every query pays a real network round trip.
Three platforms — **Memgraph, ArangoDB, FalkorDB** — are self-hosted via
Docker on the *same machine* as the benchmark client: their network round
trip is effectively **zero** by construction, not because they are
faster engines.

Rather than just disclosing this in prose, `harness/network_baseline.py`
**measures it**: a trivial no-op query (`RETURN 1`, 50 iterations, no data
touched) run against every platform before the real workloads, isolating
the pure connection/round-trip cost from actual query-engine cost. That
table is the first thing in `results/RESULTS.md`.

**How to read every latency number in this report correctly:**
subtract the relevant platform's network-baseline p50 from its measured
workload latency before comparing it to a self-hosted platform. A cloud
platform that looks "slower" on 1-hop traversal may simply be paying the
same ~20-30ms round trip it pays on the no-op query — once that's
subtracted, the actual engine-level difference may be much smaller (or
reversed). `docs/ANALYSIS.md` does this subtraction explicitly rather
than comparing raw numbers.

This asymmetry was a deliberate, documented trade-off, not an oversight:
CognoDB itself is inherently cloud-only, so a fully self-hosted line-up
would remove the one platform actually under test; a fully cloud-only
line-up would mean using less-precise, vendor-defined free-tier limits
for platforms that don't offer permanent free managed tiers, weakening
the *hardware* fairness the assignment asks for. The network baseline
above is the mitigation: it doesn't remove the asymmetry, but it makes
it measurable and correctable by the reader instead of invisible.

## Other known caveats (recorded honestly, not hidden)

- AuraDB Free's true CPU/RAM allocation isn't independently configurable
  the way the self-hosted containers are — its *advertised* free-tier
  specs are used instead of measured ones.
- Cloud regions are pinned close together (US East — see fairness table
  above) specifically to keep cross-platform network variance low between
  the two remaining cloud platforms; the self-hosted-vs-cloud gap above is
  a separate, larger effect that region-matching cannot fix.
- `point_lookup` vs `indexed_lookup` collapse to the same query on
  platforms where a full scan isn't independently triggerable — noted
  per-platform in `results/RESULTS.md` when this applies.

## Results

See [`results/RESULTS.md`](results/RESULTS.md) (generated) for the full
matrix and `results/charts/` for latency charts. **Analysis** of what the
numbers show and why is in [`docs/ANALYSIS.md`](docs/ANALYSIS.md).

## Repo layout

```
dataset/       dataset download + deterministic sampling
loaders/       one adapter per platform, all implementing base_adapter.py
workloads/     traversal / lookup / aggregation / mixed-workload logic
harness/       orchestrator (run_all.py) + report generator + metrics utils
docker-compose.yml   self-hosted platforms, resource-capped
results/       generated JSON + markdown tables + charts
docs/          methodology + analysis write-ups
```
