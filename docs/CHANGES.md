# Methodology Decision Log

Kept deliberately short — this documents *why* the setup changed during
development, not a full changelog. Transparency about pivots is part of
honest methodology reporting (assignment section 5.3).

## Memgraph: cloud → self-hosted

**Original plan:** Memgraph Cloud free tier, matching CognoDB/AuraDB as a
third managed cloud service (see README's original platform-selection
rationale — direct Bolt+Cypher comparison).

**What went wrong:** Memgraph Cloud's connection endpoint was a raw IP
address, not a DNS hostname. TLS certificate hostname verification cannot
succeed against a bare IP — the certificate is issued for a domain name —
so every connection attempt failed at the TLS handshake regardless of
credentials being correct.

**Decision:** moved Memgraph to self-hosted via `docker-compose.yml`,
capped to the same 0.5 vCPU / 256 MB as ArangoDB and FalkorDB. This also
gives Memgraph an *exact, guaranteed* resource cap rather than relying on
a cloud trial's advertised (not independently verifiable) specs — arguably
a fairness improvement, not just a workaround.

**Trade-off accepted:** the cloud-vs-self-hosted network-topology
asymmetry (see README "Known Fairness Limitation") now applies to 3 of 5
platforms instead of 2. Mitigated the same way — `harness/network_baseline.py`
measures and reports the network round-trip cost separately so it can be
subtracted out during analysis rather than silently biasing the results.
