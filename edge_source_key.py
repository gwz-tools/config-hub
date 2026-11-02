"""Extract only the pinned bootstrap RSA public key from an exact audited APK.

This authenticates the *bytes* used during the 2026-11-02 audit; it is not
independent proof of the APK publisher's identity.
"""
import base64
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

APK_SHA256 = "70df40e973a4e0af4dbd2465bb398455794117da7be6c075b3afe78d698313fb"
BOOTSTRAP_KEY_SHA256 = "7d530884a8457b8186ca0b5f41d5d412d52e052d9346c3e2ce181efa763c843c"
B64_RE = re.compile(rb"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{300,2200}={0,2}(?![A-Za-z0-9+/])")


def _canonical_key(der):
    if len(der) > 4096:
        return None
    with tempfile.TemporaryDirectory(prefix="edge-key-") as td:
        p = Path(td)
        (p / "key.der").write_bytes(der)
        result = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER",
                                 "-in", str(p / "key.der"), "-outform", "DER",
                                 "-out", str(p / "canonical.der")],
                                capture_output=True, check=False)
        if result.returncode != 0:
            return None
        return (p / "canonical.der").read_bytes()


def pinned_bootstrap_key(apk_path):
    """Return the one public RSA key matching the audited fingerprint, or fail."""
    apk = Path(apk_path)
    if not (1024 <= apk.stat().st_size <= 250 * 1024 * 1024):
        raise ValueError("APK size is outside expected bounds")
    digest = hashlib.sha256()
    with apk.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != APK_SHA256:
        raise ValueError("APK SHA256 mismatch: untrusted APK rejected")
    attempts = 0
    with zipfile.ZipFile(apk) as archive:
        for member in archive.infolist():
            if member.is_dir() or member.file_size > 64 * 1024 * 1024:
                continue
            name = member.filename.lower()
            if not (name.endswith(".dex") or name.startswith("assets/") or
                    name.endswith((".der", ".pem", ".cer", ".crt", ".json"))):
                continue
            blob = archive.read(member)
            raws = [blob] if name.endswith(".der") else []
            for match in B64_RE.finditer(blob):
                if attempts >= 400:
                    break
                attempts += 1
                try:
                    der = base64.b64decode(match.group(0), validate=True)
                except (ValueError, base64.binascii.Error):
                    continue
                if der.startswith(b"0\x82"):
                    raws.append(der)
            for raw in raws:
                canonical = _canonical_key(raw)
                if canonical and hashlib.sha256(canonical).hexdigest() == BOOTSTRAP_KEY_SHA256:
                    return canonical
    raise ValueError("Pinned bootstrap public RSA key not found in exact APK")
