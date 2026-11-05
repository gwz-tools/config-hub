#!/usr/bin/env python3
"""Deterministic, immutable-compatible routing bundle with content hashes.

Offline packaging only: does NOT push or alter live URL endpoints.
Client must fetch manifest first, verify every SHA256, validate schema and
activate ALL lists in one transaction. A VLESS URI subscription cannot
automatically change Podkop or Android routing rules.
"""
import argparse
import hashlib
import json
from pathlib import Path
from build_confirmed import read_domains, compile_confirmed


def render_bundle(direct, proxy):
    compiled = compile_confirmed(direct, proxy)
    files = {}
    for action in ("DIRECT", "PROXY", "BLOCK"):
        rows = sorted(r["domain_suffix"] for r in compiled["rules"] if r["action"] == action)
        kind = action.lower()
        files[f"{kind}.txt"] = ("\n".join(rows) + ("\n" if rows else "")).encode()
        files[f"{kind}.rule-set.json"] = (
            json.dumps({"version": 3, "rules": [{"domain_suffix": rows}] if rows else []},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_files = {
        name: {"sha256": hashlib.sha256(body).hexdigest(),
               "bytes": len(body),
               "domains": len(body.decode().splitlines()) if name.endswith(".txt") else None}
        for name, body in sorted(files.items())
    }
    version = hashlib.sha256(
        json.dumps(manifest_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    manifest = {
        "schema_version": 1, "version": version, "default_route": "PROXY",
        "update_policy": {"recommended_check_seconds": 21600,
                          "min_check_seconds": 3600,
                          "retain_last_known_good": True,
                          "atomic_activation": True},
        "files": manifest_files,
        "notes": "Paths are relative to manifest URL. Security-sensitive PROXY requires a separate fail-closed network policy.",
    }
    return files, manifest


def verify_bundle(files, manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest")
    if set(files) != set(manifest["files"]):
        raise ValueError("Incomplete routing snapshot")
    for name, meta in manifest["files"].items():
        if not isinstance(meta, dict) or type(meta.get("bytes")) is not int or not 0 <= meta["bytes"] <= 2_000_000:
            raise ValueError("Invalid or oversized file metadata")
        data = files[name]
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError("Hash/size mismatch for " + name)
    for route in ("direct", "proxy", "block"):
        expected = sorted(set(files[f"{route}.txt"].decode().splitlines()))
        ruleset = json.loads(files[f"{route}.rule-set.json"])
        if ruleset.get("version") != 3:
            raise ValueError("Bad rule-set version")
        actual = ruleset.get("rules", [])
        if actual != ([{"domain_suffix": expected}] if expected else []):
            raise ValueError("Rule-set does not match plain text")
    fingerprint = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    if manifest.get("version") != fingerprint:
        raise ValueError("Manifest version does not match declared assets")
    if manifest.get("default_route") != "PROXY":
        raise ValueError("Unexpected default route")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--direct", type=Path, default=Path("routing/confirmed-direct-20261105.txt"))
    p.add_argument("--proxy", type=Path, default=Path("routing/confirmed-proxy-20261105.txt"))
    p.add_argument("--output", type=Path, default=Path("/tmp/gwzhub-routing-bundle"))
    args = p.parse_args()
    direct, proxy = read_domains(args.direct), read_domains(args.proxy)
    files, manifest = render_bundle(direct, proxy)
    verify_bundle(files, manifest)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"version": manifest["version"], "direct": len(direct),
                      "proxy": len(proxy), "output": str(args.output)}))


if __name__ == "__main__":
    main()
