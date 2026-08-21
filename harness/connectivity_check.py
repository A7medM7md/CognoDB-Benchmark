"""
Fast connectivity diagnostic for ONE platform at a time — much quicker
than running the whole harness while you're debugging URI/scheme/network
issues.

Usage:
    python -m harness.connectivity_check cognodb
    python -m harness.connectivity_check aura
    python -m harness.connectivity_check memgraph
"""
import os
import sys
import socket
from dotenv import load_dotenv

load_dotenv()

TARGETS = {
    "cognodb": ("COGNODB_URI", "COGNODB_USER", "COGNODB_PASSWORD", "cognodb"),
    "aura": ("AURA_URI", "AURA_USER", "AURA_PASSWORD", "neo4j"),
    "memgraph": ("MEMGRAPH_URI", "MEMGRAPH_USER", "MEMGRAPH_PASSWORD", "memgraph"),
}


def parse_host_port(uri: str):
    # strip scheme
    rest = uri.split("://", 1)[-1]
    host = rest.split(":")[0].split("/")[0]
    port = 7687
    if ":" in rest.split("/")[0]:
        port = int(rest.split("/")[0].split(":")[1])
    return host, port


def check_raw_tcp(host: str, port: int):
    print(f"[1/3] Raw TCP connect to {host}:{port} ...")
    try:
        with socket.create_connection((host, port), timeout=10) as s:
            print(f"      OK — TCP handshake succeeded (no TLS yet)")
            return True
    except Exception as e:
        print(f"      FAILED: {e}")
        print("      -> if THIS fails, it's network/firewall, not the driver.")
        print("         Try: different network, disable VPN, check corporate firewall/antivirus SSL inspection.")
        return False


def check_tls(host: str, port: int):
    import ssl
    print(f"[2/3] TLS handshake to {host}:{port} ...")
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                print(f"      OK — TLS version: {ssock.version()}, cert verified")
                return True
    except ssl.SSLCertVerificationError as e:
        print(f"      FAILED (cert verification): {e}")
        print("      -> try the +ssc scheme variant (skips cert verification) to confirm it's a cert issue,")
        print("         but don't ship +ssc as your final setup — find out why the cert doesn't verify instead.")
        return False
    except Exception as e:
        print(f"      FAILED: {e}")
        print("      -> handshake started but broke — classic sign of a MITM proxy/antivirus SSL inspection.")
        return False


def check_driver(uri: str, user: str, password: str):
    from neo4j import GraphDatabase
    print(f"[3/3] Neo4j driver connect + RETURN 1 ...")
    if not password:
        print("      SKIPPED — password is empty in .env")
        return False
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        with driver.session() as s:
            s.run("RETURN 1").consume()
        driver.close()
        print("      OK — driver connected and ran a query successfully.")
        return True
    except Exception as e:
        print(f"      FAILED: {type(e).__name__}: {e}")
        return False


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in TARGETS:
        sys.exit(f"Usage: python -m harness.connectivity_check <{'|'.join(TARGETS)}>")

    key = sys.argv[1]
    uri_var, user_var, pass_var, default_user = TARGETS[key]
    uri = os.environ.get(uri_var, "")
    user = os.environ.get(user_var, default_user)
    password = os.environ.get(pass_var, "")

    if not uri:
        sys.exit(f"{uri_var} is empty in .env")

    print(f"Testing {key}: {uri}\n")
    host, port = parse_host_port(uri)

    tcp_ok = check_raw_tcp(host, port)
    if not tcp_ok:
        return
    tls_ok = check_tls(host, port)
    if not tls_ok:
        print("\n(Trying the driver anyway — it may handle the handshake differently)\n")
    check_driver(uri, user, password)


if __name__ == "__main__":
    main()
