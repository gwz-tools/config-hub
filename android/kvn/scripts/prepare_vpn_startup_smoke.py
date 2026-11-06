#!/usr/bin/env python3
"""Make a non-privileged sing-box startup probe from the real Kotlin-generated config.

Only the Android TUN inbound is replaced with a localhost SOCKS/HTTP mixed inbound,
because GitHub runners are not Android VPN environments. All DNS, routing and
outbound definitions remain unchanged to exercise engine startup semantics.
Uses the test UUID and example.com from AutoPoolTests, never user secrets.
"""
import json
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("Usage: prepare_vpn_startup_smoke.py input.json output.json")
src, dst = map(Path, sys.argv[1:])
config = json.loads(src.read_text(encoding="utf-8"))
assert len(config["inbounds"]) == 1 and config["inbounds"][0]["type"] == "tun"
config["inbounds"] = [{
    "type": "mixed", "tag": "ci-local-probe",
    "listen": "127.0.0.1", "listen_port": 20889
}]
dst.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Prepared unprivileged localhost sing-box startup probe.")
