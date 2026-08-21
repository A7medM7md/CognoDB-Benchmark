"""
Every platform adapter implements this exact interface. The harness
(harness/run_all.py) only ever talks to this interface, so every platform
runs through identical code paths — same batch sizes, same query shapes,
same timing code, same iteration counts. That's what makes the numbers
comparable instead of apples-to-oranges.
"""
from abc import ABC, abstractmethod


class GraphDBAdapter(ABC):
    name: str = "override-me"
    query_language: str = "override-me"  # e.g. "Cypher", "AQL", "Cypher (FalkorDB)"

    @abstractmethod
    def connect(self):
        """Open the connection/driver. Raise clearly if credentials are missing."""

    @abstractmethod
    def close(self):
        ...

    @abstractmethod
    def clear(self):
        """Wipe any existing data so loads are repeatable."""

    @abstractmethod
    def create_indexes(self):
        """Create the one indexed property used by the indexed-lookup workload.
        Must be called AFTER load for platforms where that's faster, but
        every adapter must end up with an index on :Person(node_id)."""

    @abstractmethod
    def load_nodes(self, node_ids: list[str], batch_size: int = 1000) -> float:
        """Bulk-insert nodes. Returns wall-clock seconds."""

    @abstractmethod
    def load_edges(self, edges: list[tuple[str, str]], batch_size: int = 1000) -> float:
        """Bulk-insert edges. Returns wall-clock seconds."""

    @abstractmethod
    def point_lookup(self, node_id: str):
        """Non-indexed style single-node fetch (e.g. full scan filter) — used
        only if the platform genuinely has no index yet; otherwise identical
        to indexed_lookup and that must be stated in the README caveats."""

    @abstractmethod
    def indexed_lookup(self, node_id: str):
        ...

    @abstractmethod
    def traverse(self, start_id: str, hops: int):
        """Return neighbors reachable in exactly `hops` hops from start_id."""

    @abstractmethod
    def aggregate_count_by_label(self):
        """Count / group-by style aggregation over the Person label."""

    @abstractmethod
    def mixed_write(self, src: str, dst: str):
        """Single write op used by the mixed read/write workload
        (e.g. MERGE a new edge)."""

    @abstractmethod
    def footprint(self) -> dict:
        """Whatever the platform exposes: stored size, memory, etc.
        Return {'metric_name': value_or_'not observable'}."""
