import time
from falkordb import FalkorDB
from .base_adapter import GraphDBAdapter

GRAPH_NAME = "benchmark"


class FalkorDBAdapter(GraphDBAdapter):
    name = "FalkorDB (self-hosted, resource-capped)"
    query_language = "Cypher (FalkorDB dialect)"

    def __init__(self, host: str, port: int, password: str | None):
        self._host = host
        self._port = port
        self._password = password
        self._client = None
        self._graph = None

    def connect(self):
        self._client = FalkorDB(host=self._host, port=self._port, password=self._password)
        self._graph = self._client.select_graph(GRAPH_NAME)

    def close(self):
        pass

    def clear(self):
        try:
            self._graph.delete()
        except Exception:
            pass  # graph didn't exist yet
        self._graph = self._client.select_graph(GRAPH_NAME)

    def create_indexes(self):
        self._graph.query("CREATE INDEX FOR (p:Person) ON (p.node_id)")

    def load_nodes(self, node_ids, batch_size=1000):
        t0 = time.perf_counter()
        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i:i + batch_size]
            rows = ", ".join(f'({{node_id: "{nid}"}})' for nid in batch)
            self._graph.query(f"UNWIND [{rows}] AS row CREATE (:Person {{node_id: row.node_id}})")
        return time.perf_counter() - t0

    def load_edges(self, edges, batch_size=1000):
        t0 = time.perf_counter()
        for i in range(0, len(edges), batch_size):
            batch = edges[i:i + batch_size]
            self._graph.query(
                """
                UNWIND $rows AS row
                MATCH (a:Person {node_id: row.src})
                MATCH (b:Person {node_id: row.dst})
                CREATE (a)-[:FOLLOWS]->(b)
                """,
                params={"rows": [{"src": s, "dst": d} for s, d in batch]},
            )
        return time.perf_counter() - t0

    def point_lookup(self, node_id):
        return self._graph.query(
            "MATCH (p:Person) WHERE p.node_id = $id RETURN p", params={"id": node_id}
        )

    def indexed_lookup(self, node_id):
        return self._graph.query(
            "MATCH (p:Person {node_id: $id}) RETURN p", params={"id": node_id}
        )

    def traverse(self, start_id, hops):
        q = f"""
            MATCH (p:Person {{node_id: $id}})-[:FOLLOWS*{hops}..{hops}]->(n)
            RETURN DISTINCT n.node_id
        """
        return self._graph.query(q, params={"id": start_id})

    def aggregate_count_by_label(self):
        return self._graph.query("MATCH (p:Person) RETURN count(p)")

    def mixed_write(self, src, dst):
        self._graph.query(
            """
            MATCH (a:Person {node_id: $src}), (b:Person {node_id: $dst})
            MERGE (a)-[:FOLLOWS]->(b)
            """,
            params={"src": src, "dst": dst},
        )

    def footprint(self):
        try:
            info = self._graph.query("CALL dbms.info()")
            return {"info": str(info)}
        except Exception:
            return {"stored_size": "not observable — check `redis-cli INFO memory` on the container"}
