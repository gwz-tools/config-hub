#!/usr/bin/env python3
"""Inspect Mamin APK without running it or exposing VPN credentials."""
import argparse
import base64
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

import mamin_verify_import as mamin

B64_RE = re.compile(rb"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{300,2200}={0,2}(?![A-Za-z0-9+/])")
MAX_MEMBER_BYTES = 64 * 1024 * 1024


def normalize_public_key(der: bytes) -> bytes | None:
    if len(der) > 4096:
        return None
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "candidate.der").write_bytes(der)
        cp = subprocess.run(
            ["openssl", "pkey", "-pubin", "-inform", "DER", "-in",
             str(p / "candidate.der"), "-outform", "DER", "-out", str(p / "canon.der")],
            capture_output=True, check=False)
        if cp.returncode:
            return None
        return (p / "canon.der").read_bytes()


def verify(key: bytes, payload: bytes, signature: bytes) -> bool:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "key.der").write_bytes(key)
        (p / "payload").write_bytes(payload)
        (p / "signature").write_bytes(signature)
        pub = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER",
                              "-in", str(p / "key.der"), "-out", str(p / "key.pem")],
                             capture_output=True)
        if pub.returncode:
            return False
        result = subprocess.run(["openssl", "dgst", "-sha256", "-verify",
                                 str(p / "key.pem"), "-signature", str(p / "signature"),
                                 str(p / "payload")], capture_output=True)
        return result.returncode == 0


def audit(path: Path):
    apk_size = path.stat().st_size
    if apk_size > 250 * 1024 * 1024 or apk_size < 1024:
        raise ValueError("Unexpected APK size")
    pinned_der = base64.b64decode(mamin.PUBLIC_KEY_DER_B64)
    pinned = normalize_public_key(pinned_der)
    if pinned is None:
        raise ValueError("Pinned key is invalid")
    keys = {}
    pinned_bytes_present = False
    scans = 0
    candidates = 0
    with zipfile.ZipFile(path) as zf:
        for item in zf.infolist():
            if item.file_size > MAX_MEMBER_BYTES or item.is_dir():
                continue
            name = item.filename.lower()
            if not (name.endswith(".dex") or name.startswith("assets/") or
                    name.endswith((".der", ".pem", ".cer", ".crt", ".json"))):
                continue
            blob = zf.read(item)
            scans += 1
            if pinned_der in blob or mamin.PUBLIC_KEY_DER_B64.encode() in blob:
                pinned_bytes_present = True
            if name.endswith(".der"):
                k = normalize_public_key(blob)
                if k:
                    keys[hashlib.sha256(k).hexdigest()] = k
            for match in B64_RE.finditer(blob):
                if candidates >= 400:
                    break
                candidates += 1
                try:
                    decoded = base64.b64decode(match.group(0), validate=True)
                except Exception:
                    continue
                if not decoded.startswith(b"0\x82"):
                    continue
                norm = normalize_public_key(decoded)
                if norm:
                    keys[hashlib.sha256(norm).hexdigest()] = norm
    print("APK SHA256:", hashlib.sha256(path.read_bytes()).hexdigest())
    print("APK size bytes:", apk_size)
    print("Scanned relevant archive members:", scans)
    print("Pinned key DER SHA256:", hashlib.sha256(pinned).hexdigest())
    print("Pinned key literally present in APK:", pinned_bytes_present)
    print("Distinct extractable RSA public keys:", len(keys))
    print("Public key fingerprints (no key contents):", sorted(keys)[:20])
    catalog = mamin.fetch_catalog()
    data = mamin.b64url(catalog.get("payload"))
    sig = mamin.b64url(catalog.get("signature"))
    print("Catalogue format/key_id:", catalog.get("format"), catalog.get("key_id"))
    print("Catalogue payload SHA256:", hashlib.sha256(data).hexdigest())
    print("Catalogue signature bytes:", len(sig))
    print("Pinned RSA signature valid:", verify(pinned, data, sig))
    found = [f for f, k in keys.items() if verify(k, data, sig)]
    print("APK candidate RSA keys verifying catalogue:", len(found))
    print("Matching public-key SHA256:", found)
    print("WARNING: key presence or one valid signature does not prove APK provenance")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", type=Path, required=True)
    args = ap.parse_args()
    audit(args.apk)
