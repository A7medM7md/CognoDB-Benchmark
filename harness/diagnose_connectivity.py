"""
Run this BEFORE harness.run_all when a cloud platform fails to connect.
It tests DNS -> TCP -> TLS as three separate steps per platform, so you
know exactly which layer is broken instead of one opaque driver error.

Usage: python -m harness.diagnose_connectivity
"""
import os
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def parse_bolt_uri(uri: str):
    # bolt+s://host:port  or  neo4j+s://host  (default port 7687)
    parsed = urlparse(uri)
    host = parsed.hostname
    port = parsed.port or 7687
    return host, port


def check(name: str, uri_env_var: str):
    uri = os.environ.get(uri_env_var, "")
    print(f"\n=== {name} ===")
    print(f"URI (from .env {uri_env_var}): {uri}")
    if not uri:
        print("  [SKIP] not set in .env")
        return

    host, port = parse_bolt_uri(uri)
    print(f"  Parsed -> host={host}  port={port}")

    # Step 1: DNS
    try:
        addrs = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        ips = sorted({a[4][0] for a in addrs})
        print(f"  [OK] DNS resolves -> {ips}")
    except socket.gaierror as e:
        print(f"  [FAIL] DNS resolution failed: {e}")
        print(f"  -> The hostname itself is wrong, or a typo, or the instance was deleted.")
        print(f"     Go back to the {name} console and copy the URI again, exactly.")
        return

    # Step 2: raw TCP
    try:
        sock = socket.create_connection((host, port), timeout=8)
        print(f"  [OK] TCP connects on port {port}")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"  [FAIL] TCP connection failed: {e}")
        print(f"  -> Port {port} is blocked (firewall/antivirus/VPN/ISP) or the instance isn't listening.")
        print(f"     - Check the instance status in the {name} console (Running vs Paused/Provisioning).")
        print(f"     - Try temporarily disabling Windows Defender Firewall / antivirus to isolate the cause.")
        print(f"     - If on a corporate/school network or VPN, outbound 7687 may be blocked — try mobile hotspot.")
        return

    # Step 3: TLS handshake, with hostname verification ON (this is what the driver does)
    ctx = ssl.create_default_context()
    try:
        with ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
            cert = tls_sock.getpeercert()
            cn = dict(x[0] for x in cert.get("subject", [])).get("commonName", "?")
            sans = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
            print(f"  [OK] TLS handshake succeeds")
            print(f"       Certificate CN={cn}  SAN={sans}")
    except ssl.SSLCertVerificationError as e:
        print(f"  [FAIL] TLS certificate verification failed: {e}")
        if host.replace(".", "").isdigit():
            print(f"  -> You're connecting to a raw IP ({host}). TLS certs are issued for domain")
            print(f"     names, not IPs, so hostname verification will ALWAYS fail against an IP.")
            print(f"     Go back to the console and look for a DNS hostname instead of the IP —")
            print(f"     most managed platforms give you one specifically for this reason.")
        else:
            print(f"  -> The cert doesn't match '{host}'. Double-check you copied the exact")
            print(f"     hostname from the console (no typos, no manual edits).")
    except ssl.SSLError as e:
        print(f"  [FAIL] TLS handshake failed (not a cert issue): {e}")
        print(f"  -> Something between you and the server is interfering with TLS —")
        print(f"     common causes: antivirus 'HTTPS scanning'/SSL inspection, corporate proxy,")
        print(f"     or a captive-portal network. Try a different network (mobile hotspot) to confirm.")
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    check("CognoDB Cloud", "COGNODB_URI")
    check("Neo4j AuraDB Free", "AURA_URI")
    check("Memgraph Cloud", "MEMGRAPH_URI")
    print("\nDone. Fix whatever failed above, then re-run: python -m harness.run_all")
