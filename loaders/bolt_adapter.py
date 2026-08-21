"""
One adapter implementation for every bolt+Cypher platform: CognoDB,
Neo4j AuraDB Free, and Memgraph Cloud all speak the same wire protocol
and accept the same Cypher, so they share this code. This is itself
a fairness point worth calling out in the README — it removes "we wrote
the query differently for each platform" as a confound for these three.
"""
import time
from neo4j import GraphDatabase
from .base_adapter import GraphDBAdapter


class BoltCypherAdapter(GraphDBAdapter):
    query_language = "Cypher"

    def __init__(self, name: str, uri: str, user: str, password: str):
        self.name = name
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None

    def connect(self):
        if self._password:
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        else:
            # self-hosted platforms (e.g. Memgraph in docker-compose) have no
            # auth configured by default — connect unauthenticated instead of
            # forcing a password that doesn't exist for that deployment
            self._driver = GraphDatabase.driver(self._uri, auth=None)
        self._driver.verify_connectivity()

    def close(self):
        if self._driver:
            self._driver.close()

    def clear(self):
        with self._driver.session() as s:
            # batched delete so we don't blow memory limits on the free tier
            while True:
                result = s.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS c"
                )
                if result.single()["c"] == 0:
                    break

    def create_indexes(self):
        with self._driver.session() as s:
            s.run("CREATE INDEX person_node_id IF NOT EXISTS FOR (p:Person) ON (p.node_id)")

    def load_nodes(self, node_ids, batch_size=1000):
        t0 = time.perf_counter()
        with self._driver.session() as s:
            for i in range(0, len(node_ids), batch_size):
                batch = node_ids[i:i + batch_size]
                s.run(
                    "UNWIND $ids AS id CREATE (:Person {node_id: id})",
                    ids=batch,
                )
        return time.perf_counter() - t0

    def load_edges(self, edges, batch_size=1000):
        t0 = time.perf_counter()
        with self._driver.session() as s:
            for i in range(0, len(edges), batch_size):
                batch = [{"src": s_, "dst": d_} for s_, d_ in edges[i:i + batch_size]]
                s.run(
                    """
                    UNWIND $rows AS row
                    MATCH (a:Person {node_id: row.src})
                    MATCH (b:Person {node_id: row.dst})
                    CREATE (a)-[:FOLLOWS]->(b)
                    """,
                    rows=batch,
                )
        return time.perf_counter() - t0

    def point_lookup(self, node_id):
        with self._driver.session() as s:
            return s.run(
                "MATCH (p:Person) WHERE p.node_id = $id RETURN p", id=node_id
            ).single()

    def indexed_lookup(self, node_id):
        with self._driver.session() as s:
            return s.run(
                "MATCH (p:Person {node_id: $id}) RETURN p", id=node_id
            ).single()

    def traverse(self, start_id, hops):
        with self._driver.session() as s:
            q = f"""
                MATCH (p:Person {{node_id: $id}})-[:FOLLOWS*{hops}..{hops}]->(n)
                RETURN DISTINCT n.node_id AS id
            """
            return [r["id"] for r in s.run(q, id=start_id)]

    def aggregate_count_by_label(self):
        with self._driver.session() as s:
            return s.run(
                "MATCH (p:Person) RETURN count(p) AS total"
            ).single()["total"]

    def mixed_write(self, src, dst):
        with self._driver.session() as s:
            s.run(
                """
                MATCH (a:Person {node_id: $src}), (b:Person {node_id: $dst})
                MERGE (a)-[:FOLLOWS]->(b)
                """,
                src=src, dst=dst,
            )

    def footprint(self):
        # Bolt protocol has no universal storage-size call; each managed
        # platform exposes this differently (Aura console, Memgraph metrics
        # endpoint, CognoDB console). Report console-observed values manually
        # in results/raw and note 'not observable via driver' here.
        return {"stored_size": "not observable via bolt driver — see console"}
