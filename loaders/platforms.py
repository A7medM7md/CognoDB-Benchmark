"""
Central registry of the 5 platforms under test. Import get_platforms()
from the harness — nothing else should hardcode platform wiring.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from .bolt_adapter import BoltCypherAdapter
from .arangodb_adapter import ArangoDBAdapter
from .falkordb_adapter import FalkorDBAdapter

# Explicit path instead of relying on cwd auto-discovery — load_dotenv()
# with no args only finds .env if you happen to run the command from the
# exact project root; this works no matter where you invoke python from.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

if not ENV_PATH.exists():
    sys.exit(
        f"\nNo .env file found at: {ENV_PATH}\n"
        f"Fix: copy .env.example to .env in that exact folder "
        f"(not .env.txt, not .env.example — must be named exactly '.env'),\n"
        f"then fill in your real credentials.\n"
    )

load_dotenv(dotenv_path=ENV_PATH)

REQUIRED_VARS = [
    "COGNODB_URI", "COGNODB_PASSWORD",
    "AURA_URI", "AURA_PASSWORD",
]
missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
if missing:
    sys.exit(
        f"\n.env found at {ENV_PATH} but missing/empty: {', '.join(missing)}\n"
        f"Open that file and make sure every line has a real value after the '='.\n"
    )


def get_platforms():
    return {
        "cognodb": BoltCypherAdapter(
            name="CognoDB Cloud",
            uri=os.environ["COGNODB_URI"],
            user=os.environ.get("COGNODB_USER", "cognodb"),
            password=os.environ.get("COGNODB_PASSWORD", ""),
        ),
        "aura": BoltCypherAdapter(
            name="Neo4j AuraDB Free",
            uri=os.environ["AURA_URI"],
            user=os.environ.get("AURA_USER", "neo4j"),
            password=os.environ.get("AURA_PASSWORD", ""),
        ),
        "memgraph": BoltCypherAdapter(
            name="Memgraph (self-hosted, resource-capped)",
            uri=os.environ.get("MEMGRAPH_URI", "bolt://localhost:7688"),
            user="",
            password="",  # no auth configured on the self-hosted container
        ),
        "arangodb": ArangoDBAdapter(
            url=os.environ.get("ARANGO_URL", "http://localhost:8529"),
            user=os.environ.get("ARANGO_USER", "root"),
            password=os.environ.get("ARANGO_PASSWORD", ""),
            db_name=os.environ.get("ARANGO_DB", "benchmark"),
        ),
        "falkordb": FalkorDBAdapter(
            host=os.environ.get("FALKORDB_HOST", "localhost"),
            port=int(os.environ.get("FALKORDB_PORT", 6379)),
            password=os.environ.get("FALKORDB_PASSWORD") or None,
        ),
    }
