import time
from arango import ArangoClient
from .base_adapter import GraphDBAdapter


class ArangoDBAdapter(GraphDBAdapter):
    name = "ArangoDB (self-hosted, resource-capped)"
    query_language = "AQL"

    def __init__(self, url: str, user: str, password: str, db_name: str):
        self._url = url
        self._user = user
        self._password = password
        self._db_name = db_name
        self._client = None
        self._db = None

    def connect(self):
        self._client = ArangoClient(hosts=self._url)
        sys_db = self._client.db("_system", username=self._user, password=self._password)
        if not sys_db.has_database(self._db_name):
            sys_db.create_database(self._db_name)
        self._db = self._client.db(self._db_name, username=self._user, password=self._password)
        if not self._db.has_collection("Person"):
            self._db.create_collection("Person")
        if not self._db.has_collection("FOLLOWS"):
            self._db.create_collection("FOLLOWS", edge=True)

    def close(self):
        pass  # python-arango has no persistent connection to close

    def clear(self):
        self._db.collection("Person").truncate()
        self._db.collection("FOLLOWS").truncate()

    def create_indexes(self):
        self._db.collection("Person").add_persistent_index(fields=["node_id"], unique=True)

    def load_nodes(self, node_ids, batch_size=1000):
        col = self._db.collection("Person")
        t0 = time.perf_counter()
        for i in range(0, len(node_ids), batch_size):
            batch = [{"_key": nid, "node_id": nid} for nid in node_ids[i:i + batch_size]]
            col.insert_many(batch, overwrite=True)
        return time.perf_counter() - t0

    def load_edges(self, edges, batch_size=1000):
        col = self._db.collection("FOLLOWS")
        t0 = time.perf_counter()
        for i in range(0, len(edges), batch_size):
            batch = [
                {"_from": f"Person/{s}", "_to": f"Person/{d}"}
                for s, d in edges[i:i + batch_size]
            ]
            col.insert_many(batch, overwrite=False)
        return time.perf_counter() - t0

    def point_lookup(self, node_id):
        cursor = self._db.aql.execute(
            "FOR p IN Person FILTER p.node_id == @id RETURN p", bind_vars={"id": node_id}
        )
        return list(cursor)

    def indexed_lookup(self, node_id):
        return self._db.collection("Person").get(node_id)

    def traverse(self, start_id, hops):
        cursor = self._db.aql.execute(
            f"""
            FOR v IN {hops}..{hops} OUTBOUND @start FOLLOWS
              OPTIONS {{uniqueVertices: 'global', bfs: true}}
              RETURN DISTINCT v.node_id
            """,
            bind_vars={"start": f"Person/{start_id}"},
        )
        return list(cursor)

    def aggregate_count_by_label(self):
        cursor = self._db.aql.execute("RETURN LENGTH(Person)")
        return list(cursor)[0]

    def mixed_write(self, src, dst):
        self._db.aql.execute(
            """
            UPSERT { _from: @from, _to: @to }
            INSERT { _from: @from, _to: @to }
            UPDATE {} IN FOLLOWS
            """,
            bind_vars={"from": f"Person/{src}", "to": f"Person/{dst}"},
        )

    def footprint(self):
        try:
            stats = self._db.collection("Person").statistics()
            return {"figures": stats.get("figures", "not observable")}
        except Exception:
            return {"stored_size": "not observable"}
