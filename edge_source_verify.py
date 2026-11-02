#!/usr/bin/env python3
"""Verify a pinned signed Android bootstrap with RS256 with an exact hash-pinned APK key.

The key is selected by the audited APK SHA256 and bootstrap public key SHA256;
this is not independent proof of the APK publisher identity.

Fail-closed signature and timestamp validation; writes only requested verified candidate files.
Usage: python3 edge_source_verify.py [--output-dir /opt/gwzhub/data]
Requires: Python 3 stdlib and openssl command-line.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys
import urllib.request
from urllib.parse import urlsplit, parse_qs

CATALOG_URL = "https://mamin-starter-catalogue.surge.sh/bootstrap/android-v2.json"
KEY_ID = "bootstrap-7d530884a8457b81"
PUBLIC_KEY_DER_B64 = "MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEArcMO0d87NrTGvF0b83KwuJzQ4hGvKeysi/c6HpdZ6MHkqZ1CPX5LHnomzOQjDUL9Cm5nhp8Qxx5BYwXFY/lJl+WGdY8IvQ46i2tX/BT+Blw8dNhQjjBKaGQeWd9LFv3LGlJgc6jU5V+Ug+wjbZkgX6jO88C9XjMUpIcPi30UXbFIWKf8IC4vXnjr/++MAjj34cDD39bY8juOKmblrDOHm/3RYY0iSi/0+M2Bd63puFSiIihtwCRWAUw/jjpochGt2+khDWLT9BJscJIfGluXq1WfDQl7GjqrP+GM79QXa7m8dYOqC3WgjlR0zM5QnOIY3fi5UPyOgOPIJTBcbMSDfxQAwfwIQkKg/oSJgbQfbWGoQdkg9PnOpRfpjq+CYVcEgZux7cD1khbzStHxBOoXZ1zA5siAPR3qhAyIb0ZWya7ASK8xUAm5cvVLBFrAG7+v4C6hyFUGAPnf5aO8BPszMgRRcR3Os0RR6vSckUOkfS/uzdx/Vhw1X8wFqGuDCH2RAgMBAAE="
MAX_HTTP_BYTES = 1048576


def b64url(s):
    if not isinstance(s, str) or len(s) > 1000000:
        raise ValueError("Invalid Base64URL field")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_rs256(payload, signature, public_key_der=None):
    if not shutil.which("openssl"):
        raise RuntimeError("openssl executable not found")
    with tempfile.TemporaryDirectory(prefix="edge-signature-") as td:
        p = Path(td)
        (p / "key.der").write_bytes(public_key_der if public_key_der is not None else base64.b64decode(PUBLIC_KEY_DER_B64))
        (p / "payload.bin").write_bytes(payload)
        (p / "signature.bin").write_bytes(signature)
        pub = subprocess.run([
            "openssl", "pkey", "-pubin", "-inform", "DER", "-in", str(p / "key.der"),
            "-out", str(p / "key.pem")], capture_output=True, text=True)
        if pub.returncode:
            raise RuntimeError("Cannot read pinned public key: " + pub.stderr.strip())
        checked = subprocess.run([
            "openssl", "dgst", "-sha256", "-verify", str(p / "key.pem"),
            "-signature", str(p / "signature.bin"), str(p / "payload.bin")],
            capture_output=True, text=True)
        if checked.returncode != 0 or "Verified OK" not in checked.stdout:
            raise ValueError("RS256 signature INVALID: catalogue rejected")


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".edge-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fetch_catalog():
    req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "RelayVerifier/1.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        if not res.geturl().startswith("https://"):
            raise ValueError("Redirect to insecure URL blocked")
        content = res.read(MAX_HTTP_BYTES + 1)
    if len(content) > MAX_HTTP_BYTES:
        raise ValueError("Catalogue too large")
    return json.loads(content)


def vetted_nodes(data):
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or len(nodes) > 10000:
        raise ValueError("Invalid nodes list")
    selected = []
    seen = set()
    for item in nodes:
        if not isinstance(item, str) or len(item) > 4096 or not item.startswith(("vless://", "trojan://", "ss://")):
            continue
        try:
            p = urlsplit(item)
            if not p.hostname or p.port is None or not (1 <= p.port <= 65535):
                continue
        except ValueError:
            continue
        if item not in seen:
            seen.add(item)
            selected.append(item)
    if not selected:
        raise ValueError("Verified catalogue contains no supported nodes")
    return selected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="/opt/gwzhub/data", help="Where to place verified candidate files")
    ap.add_argument("--catalog-file", help="Optional local JSON for offline validation")
    ap.add_argument("--apk-file", help="Exact hash-pinned source APK supplying bootstrap RSA key")
    ap.add_argument("--diagnose", action="store_true", help="Show safe signature metadata on failure")
    a = ap.parse_args()
    root = Path(a.output_dir)
    catalog = json.loads(Path(a.catalog_file).read_text()) if a.catalog_file else fetch_catalog()
    if (catalog.get("format"), catalog.get("algorithm"), catalog.get("key_id")) != ("mamin-bootstrap-v2", "RS256", KEY_ID):
        raise ValueError("Unexpected format/algorithm/key_id")
    payload = b64url(catalog.get("payload"))
    signature = b64url(catalog.get("signature"))
    public_key_der = None
    if a.apk_file:
        from edge_source_key import pinned_bootstrap_key
        public_key_der = pinned_bootstrap_key(a.apk_file)
    try:
        verify_rs256(payload, signature, public_key_der=public_key_der)
    except (ValueError, RuntimeError):
        if a.diagnose:
            # Never print VPN links, signed payload bytes or credentials.
            pinned_key = public_key_der if public_key_der is not None else base64.b64decode(PUBLIC_KEY_DER_B64)
            print("RS256 audit: FAIL CLOSED", file=sys.stderr)
            print("Pinned key_id:", KEY_ID, file=sys.stderr)
            print("Pinned public key DER SHA256:", hashlib.sha256(pinned_key).hexdigest(), file=sys.stderr)
            print("Payload SHA256:", hashlib.sha256(payload).hexdigest(), file=sys.stderr)
            print("Signature bytes:", len(signature),
                  "(pinned RSA key: 3072 bit; expected signature: 384 bytes)",
                  file=sys.stderr)
            print("Compare key against bootstrap signing key extracted from APK; "
                  "never import an unauthenticated replacement key from catalogue.",
                  file=sys.stderr)
        raise
    data = json.loads(payload.decode("utf-8"))
    if data.get("kind") != "mamin-bootstrap-v2" or data.get("package") != "app.mamin.vpn" or data.get("schema") != 1:
        raise ValueError("Unexpected signed payload type")
    now = int(time.time())
    issued = data.get("issued_at")
    expiry = data.get("expires_at")
    sequence = data.get("sequence")
    if not all(type(x) is int for x in (issued, expiry, sequence)):
        raise ValueError("Missing / invalid timestamps or sequence")
    if issued > now + 300 or expiry <= now or expiry < issued:
        raise ValueError("Catalogue not valid at current system time")
    state_path = root / "edge-catalogue-sequence.json"
    old_sequence = -1
    old_hash = None
    payload_hash = hashlib.sha256(payload).hexdigest()
    if state_path.exists():
        state = json.loads(state_path.read_text())
        old_sequence = int(state.get("sequence", -1))
        old_hash = state.get("payload_sha256")
    if sequence < old_sequence or (sequence == old_sequence and old_hash and old_hash != payload_hash):
        raise ValueError("Catalogue rollback / sequence reuse detected")
    nodes = vetted_nodes(data)
    reality=[]
    for uri in nodes:
        if not uri.startswith("vless://"):
            continue
        if parse_qs(urlsplit(uri).query).get("security", [""])[0].lower() == "reality":
            reality.append(uri)
    # The existing GWZHUB checker handles VLESS Reality; do not push SS/Trojan to it.
    if not reality:
        raise ValueError("No VLESS Reality candidates compatible with current GWZHUB checker")
    atomic_write(root / "edge-candidates.verified.txt", ("\n".join(nodes) + "\n").encode())
    atomic_write(root / "edge-vless-reality.verified.txt", ("\n".join(reality) + "\n").encode())
    atomic_write(state_path, json.dumps({"sequence": sequence, "expires_at": expiry,
                                         "payload_sha256": payload_hash},
                                        ensure_ascii=False, indent=2).encode())
    from collections import Counter
    print("RS256: VERIFIED; format/expiry/sequence: OK")
    print("RSA key source:", "exact audited APK SHA256" if a.apk_file else "legacy candidate (for unit testing)")
    print("All nodes:", len(nodes), dict(Counter(x.split("://", 1)[0] for x in nodes)))
    print("VLESS Reality candidates:", len(reality))
    print("Output:", root / "edge-vless-reality.verified.txt")
    print("Existing checker, DB, live subscriptions and Podkop unchanged")


if __name__ == "__main__":
    main()