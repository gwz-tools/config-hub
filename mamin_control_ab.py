#!/usr/bin/env python3
"""Safe A/B control for Mamin 0/12 on GWZHUB.

Test existing publicly published cloud-vless.txt using exactly the same
local sing-box diagnostic code as Mamin. Never print URLs, credentials,
server names, or IP addresses. No changes to private feed/sequence, routers,
cron or live processes.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

# The detailed diagnostic is staged in /tmp and the parser on the GWZHUB host.
sys.path.insert(0, "/tmp")
sys.path.insert(0, "/opt/gwzhub/mamin-source")
from cloud_verified import unique_candidates
from mamin_hub_diagnose import inspect_one

CONTROL_URL = "https://raw.githubusercontent.com/gwz-tools/config-hub/main/cloud-vless.txt"
MAX_BYTES = 1024 * 1024
SING_BOX = "/opt/gwzhub/mamin-source/bin/sing-box"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--control-file", type=Path,
                        help="Optional local verified pool file, instead of public Config Hub cloud feed")
    parser.add_argument("--sing-box", default=SING_BOX)
    args = parser.parse_args()
    if not 1 <= args.max_candidates <= 20:
        parser.error("--max-candidates must be 1..20")
    if not Path(args.sing_box).is_file():
        parser.error("Private sing-box binary not found")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="mamin-control-") as td:
        tmp = Path(td) / "control.txt"
        if args.control_file:
            data = args.control_file.read_bytes()
        else:
            with urlopen(Request(CONTROL_URL, headers={"User-Agent": "GWZHUB-MaminAB/1.0"}), timeout=25) as response:
                if not response.geturl().startswith("https://"):
                    raise SystemExit("Unsafe redirect")
                data = response.read(MAX_BYTES + 1)
        if not 0 < len(data) <= MAX_BYTES:
            raise SystemExit("Invalid control feed length")
        tmp.write_bytes(data)
        os.chmod(tmp, 0o600)
        links = unique_candidates(tmp, args.max_candidates)
        if not links:
            raise SystemExit("No parser-compatible control nodes")
        counters = Counter()
        for link in links:
            counters["checked"] += 1
            counters.update(inspect_one(link, args.sing_box))
    print(json.dumps({
        "sample": "existing_Config_Hub_cloud_VLESS" if not args.control_file else "local_existing_VLESS",
        "control_nodes_tested": counters["checked"],
        "stage_counts_only": dict(sorted(counters.items())),
        "mamin_reference_previous_test": {"nodes_checked": 12, "control_https_ok": 0},
        "interpretation": {
            "control_https_ok_above_zero": "Tester can pass through a non-Mamin VLESS; Mamin reachability/credentials differ",
            "control_https_zero": "Inconclusive: control feed may also fail here; inspect local tunnel/network path",
        },
        "credentials_printed": False,
        "local_config_changed": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
