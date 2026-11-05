#!/usr/bin/env python3
"""Optional OpenRay quality audit. Never publishes node credentials or changes subscriptions."""
import argparse
import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

ALLOWED_HOST = "raw.githubusercontent.com"
SCHEMES = ("vless://",)


def candidate_fingerprint(line):
    url = urlsplit(line.strip())
    if url.scheme != "vless" or not url.hostname or not url.port or not url.username:
        raise ValueError("invalid vless endpoint")
    if not (1 <= url.port <= 65535):
        raise ValueError("invalid port")
    UUID(url.username)
    if url.password:
        raise ValueError("unexpected password in URI authority")
    host = url.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("local hostname")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr is not None and not addr.is_global:
        raise ValueError("non-global endpoint")
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", host):
        raise ValueError("invalid host")
    q = parse_qs(url.query)
    if q.get("allowInsecure", ["0"])[0].lower() in ("1", "true"):
        raise ValueError("insecure TLS")
    if q.get("security", ["none"])[0] not in ("tls", "reality"):
        raise ValueError("unsupported security")
    if q.get("type", ["tcp"])[0] not in ("tcp", "raw", "ws", "grpc"):
        raise ValueError("unsupported transport")
    if q.get("security", ["none"])[0] == "reality" and not q.get("pbk", [""])[0]:
        raise ValueError("reality missing public key")
    # Dedup by configuration, ignoring comment/fragment and query-param ordering.
    canonical = (host, url.port, url.username.lower(),
                 tuple(sorted((k, tuple(sorted(v))) for k, v in q.items())))
    digest = hashlib.sha256(repr(canonical).encode()).hexdigest()
    return digest


def audit(text, limits):
    rows = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if len(rows) < limits["min_total_lines"]:
        raise ValueError("suspiciously short source")
    seen = set()
    counts = {"lines": len(rows), "vless_seen": 0, "vless_valid": 0,
              "vless_invalid": 0, "vless_duplicate": 0,
              "other_protocols": 0, "ru_label_rejected": 0}
    for row in rows:
        if not row.startswith(SCHEMES):
            counts["other_protocols"] += 1
            continue
        counts["vless_seen"] += 1
        # Geo labels are only negative hints. A positive exit-country check is mandatory downstream.
        fragment = urlsplit(row).fragment.lower()
        if re.search(r"(?:^|[^a-z])(?:russia|russian|ru)(?:$|[^a-z])", fragment) or "🇷🇺" in fragment:
            counts["ru_label_rejected"] += 1
            continue
        try:
            key = candidate_fingerprint(row)
        except (ValueError, TypeError):
            counts["vless_invalid"] += 1
            continue
        if key in seen:
            counts["vless_duplicate"] += 1
            continue
        seen.add(key)
        counts["vless_valid"] += 1
    if not limits["min_vless_candidates"] <= counts["vless_valid"] <= limits["max_vless_candidates"]:
        raise ValueError("VLESS candidate count outside expected bounds")
    return counts


def fetch(url, max_bytes, timeout):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.username or parsed.password:
        raise ValueError("Unapproved source origin")
    req = Request(url, headers={"User-Agent": "GWZHUB-OpenRay-Audit/1.0"})
    with urlopen(req, timeout=timeout) as response:
        final = urlsplit(response.url)
        if final.scheme != "https" or final.hostname != ALLOWED_HOST:
            raise ValueError("Unapproved redirect")
        if response.status != 200:
            raise ValueError("Unexpected HTTP status")
        ctype = response.headers.get("Content-Type", "").lower()
        if "html" in ctype:
            raise ValueError("HTML is not a subscription")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("Source exceeds byte cap")
    return body.decode("utf-8", "strict")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="optional_sources/openray.json")
    parser.add_argument("--output", default="/tmp/gwzhub-openray-audit.json")
    args = parser.parse_args()
    conf = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if conf["enabled_for_production"]:
        raise ValueError("Audit-only job must not enable production sources")
    text = fetch(conf["url"], conf["max_download_bytes"], conf["network_timeout_seconds"])
    counts = audit(text, conf)
    report = {"source": conf["name"], "origin": conf["source_repository"],
              "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "counts": counts,
              "status": "AUDIT_ONLY_NOT_TUNNEL_VERIFIED",
              "note": "No node URIs or credentials saved. Geo/exit IP, Russia reachability and HTTPS tunnels not checked."}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": counts}))


if __name__ == "__main__":
    main()
