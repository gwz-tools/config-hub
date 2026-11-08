#!/usr/bin/env python3
"""Validate bundled, immutable routing snapshot. Does not contact VPN servers."""
import hashlib
import json
from pathlib import Path

assets = Path(__file__).resolve().parents[1] / "app/src/main/assets/routing"
m = json.loads((assets / "manifest.json").read_text(encoding="utf-8"))
assert m.get("schema_version") == 1 and m.get("default_route") == "PROXY"
assert set(m["files"]) == {
    "direct.txt", "proxy.txt", "block.txt", "direct.rule-set.json",
    "proxy.rule-set.json", "block.rule-set.json",
}
for name, meta in m["files"].items():
    data = (assets / name).read_bytes()
    assert len(data) == meta["bytes"], name
    assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
for name in ("direct", "proxy", "block"):
    text=(assets/f"{name}.txt").read_text(encoding="utf-8").splitlines()
    assert text==sorted(set(text)), name
    js=json.loads((assets/f"{name}.rule-set.json").read_text(encoding="utf-8"))
    assert js["version"]==3
    assert js["rules"]==([{"domain_suffix":text}] if text else []),name
assert len((assets/"direct.txt").read_text().splitlines()) > 0
assert len((assets/"proxy.txt").read_text().splitlines()) > 0
print("Bundled routing assets verified: version",m["version"])
