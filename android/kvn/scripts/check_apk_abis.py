#!/usr/bin/env python3
"""Verify ABI split APK outputs: no 4-architecture libbox in a phone install."""
import hashlib
import sys
from pathlib import Path
from zipfile import ZipFile

ABIS = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")


def main(output_dir: Path) -> None:
    for abi in ABIS:
        apk = output_dir / f"app-{abi}-debug.apk"
        if not apk.is_file():
            raise SystemExit(f"Missing expected {abi} Android APK: {apk}")
        with ZipFile(apk) as package:
            native = [
                name for name in package.namelist()
                if name.startswith("lib/") and name.endswith(".so")
            ]
        expected = f"lib/{abi}/libbox.so"
        if expected not in native:
            raise SystemExit(f"Missing native VPN engine {expected} in {apk.name}")
        unexpected = [name for name in native if not name.startswith(f"lib/{abi}/")]
        if unexpected:
            raise SystemExit(f"Unexpected ABI libraries in {apk.name}: {unexpected}")
        size = apk.stat().st_size
        if size > 130_000_000:
            raise SystemExit(f"{apk.name} is unexpectedly large ({size:,} bytes)")
        digest = hashlib.sha256(apk.read_bytes()).hexdigest()
        (output_dir / (apk.name + ".sha256")).write_text(
            f"{digest}  {apk.name}\n", encoding="ascii"
        )
        print(f"{abi}: {size / 1_000_000:.2f} MB | sha256 {digest}")
    print("All four ABI-specific builds contain exactly their own native VPN libraries.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_apk_abis.py OUTPUT_APK_DIRECTORY")
    main(Path(sys.argv[1]))
