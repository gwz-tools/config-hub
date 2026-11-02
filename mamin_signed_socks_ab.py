#!/usr/bin/env python3
"""Read-only authenticated Mamin RS256 catalogue probe through SOCKS5.

Only APK-pinned signed fresh catalogue; no feed publishing, cron, router changes.
No VLESS endpoints, UUIDs, or key values emitted.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

SOURCE_DIR = Path("/opt/gwzhub/mamin-source")
APK = Path("/opt/gwzhub/data/mamin/Mamin-VPN-0.9.29.apk")
STATE = Path("/opt/gwzhub/data/mamin/mamin-catalogue-sequence.json")
BIN = "/opt/gwzhub/mamin-source/bin/sing-box-1.14.2"
IMPORT = SOURCE_DIR / "mamin_verify_import.py"

sys.path.insert(0, "/tmp")
sys.path.insert(1, str(SOURCE_DIR))

from cloud_verified import unique_candidates
from gwzhub_socks_vless_check import check_link


def main():
    if os.geteuid() != 0:
        raise SystemExit("Use sudo; all credentials remain local.")
    if not APK.is_file() or not IMPORT.is_file() or not Path(BIN).is_file():
        raise SystemExit("Pinned APK, verifier or isolated sing-box missing.")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="mamin-signed-socks-") as directory:
        temp = Path(directory)
        if STATE.is_file():
            shutil.copyfile(STATE, temp / STATE.name)
            os.chmod(temp / STATE.name, 0o600)
        proc = subprocess.run(
            [sys.executable, str(IMPORT), "--output-dir", str(temp),
             "--apk-file", str(APK)],
            capture_output=True, text=True, timeout=80
        )
        if proc.returncode:
            print(json.dumps({
                "signed_catalogue": "REJECTED; no servers tested",
                "error_category": "verification_or_freshness_failure",
                "live_services_changed": False,
                "private_feed_changed": False,
                "credentials_printed": False,
            }, indent=2))
            return 2
        source = temp / "mamin-vless-reality.verified.txt"
        lines = unique_candidates(source, 12)
        counts = Counter()
        for link in lines:
            counts["checked"] += 1
            counts.update(check_link(link, BIN))
        print(json.dumps({
            "signed_catalogue": "APK-pinned RS256 verified; freshness and sequence validated",
            "test_method": "sing-box 1.14.2 SOCKS5 with proxy-resolved hostname",
            "stage_counts_only": dict(sorted(counts.items())),
            "no_publication": True,
            "live_services_changed": False,
            "private_feed_changed": False,
            "credentials_printed": False,
        }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
