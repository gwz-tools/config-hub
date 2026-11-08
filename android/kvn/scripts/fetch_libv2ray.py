#!/usr/bin/env python3
"""Download the original AndroidLibXrayLite v26.9.30 AAR with SHA-256 pin.

The byte-identical patched Mamin VPN native binary is deliberately NOT bundled.
This library is LGPL-3.0 and Xray-core is MPL-2.0; keep license notices.
"""
from __future__ import annotations
import hashlib
import pathlib
import urllib.request

VERSION = "v26.9.30"
SHA256 = "cf71680b776b9ca583747ba652f816b047a655eab875d8951e6141636d88bbd6"
URL = f"https://github.com/2dust/AndroidLibXrayLite/releases/download/{VERSION}/libv2ray.aar"
TARGET = pathlib.Path(__file__).resolve().parents[1] / "app" / "libs" / "libv2ray.aar"

def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.is_file() and digest(TARGET) == SHA256:
        print("Using SHA-256 verified AndroidLibXrayLite", VERSION)
        return
    temp = TARGET.with_suffix(".part")
    temp.unlink(missing_ok=True)
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "KVN-Xray-CI/0.1.14"})
        with urllib.request.urlopen(req, timeout=120) as inp, temp.open("wb") as out:
            if not inp.geturl().startswith("https://"):
                raise ValueError("Insecure redirect")
            for part in iter(lambda: inp.read(1024 * 1024), b""):
                out.write(part)
                if out.tell() > 85000000:
                    raise ValueError("Unexpected AAR size")
        if digest(temp) != SHA256:
            raise ValueError("libv2ray AAR digest mismatch")
        temp.replace(TARGET)
        print("Verified AndroidLibXrayLite", VERSION, SHA256)
    finally:
        temp.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
