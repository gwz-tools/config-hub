#!/usr/bin/env python3
"""Compile staged, explicit routing policy. No production subscription changes."""
import argparse
import ipaddress
import json
import re
from pathlib import Path

FIELDS = ("direct_domains", "proxy_domains", "block_domains")
ROUTES = {"direct_domains": "DIRECT", "proxy_domains": "PROXY", "block_domains": "BLOCK"}
CHECK_DOMAINS = {"ifconfig.me", "ipify.org", "checkip.amazonaws.com"}


def domain(value):
    if not isinstance(value, str):
        raise ValueError("Domain must be a string")
    value = value.strip().lower().rstrip(".")
    if value.startswith("*."):
        value = value[2:]
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Bad IDN domain") from exc
    if (len(value) > 253 or "." not in value or
        not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", p) for p in value.split("."))):
        raise ValueError("Bad domain: " + value)
    return value


def matches(host, suffix):
    return host == suffix or host.endswith("." + suffix)


def compile_policy(policy):
    if policy.get("default_public_route") != "PROXY":
        raise ValueError("Unrecognized default route")
    rules, conflicts = {}, []
    for field in FIELDS:
        for raw in policy.get(field, []):
            host = domain(raw)
            if host in rules and rules[host] != ROUTES[field]:
                conflicts.append({"domain": host, "routes": sorted({rules[host], ROUTES[field]})})
            rules[host] = ROUTES[field]
    if conflicts:
        raise ValueError("Conflicting exact rules: " + json.dumps(conflicts))
    if any(matches(host, d) for host in rules if rules[host] == "DIRECT" for d in CHECK_DOMAINS):
        raise ValueError("IP check service cannot be forced DIRECT")
    reviews = sorted({domain(v) for v in policy.get("review_direct_candidates", [])})
    shadow = [{"specific": a, "general": b, "specific_route": rules[a], "general_route": rules[b]}
              for a in sorted(rules) for b in sorted(rules)
              if a != b and matches(a, b) and rules[a] != rules[b]]
    return {"schema_version": 1, "default": "PROXY", "rules": [
        {"domain_suffix": d, "action": action, "include_apex": True}
        for d, action in sorted(rules.items(), key=lambda v: (-len(v[0].split(".")), -len(v[0]), v[0]))
    ], "review_candidates": reviews, "overrides": shadow,
        "note": "Domain suffix uses label boundary; longer suffix takes precedence. Not active Podkop config."}


def route(hostname, compiled):
    host = domain(hostname)
    for rule in compiled["rules"]:
        if matches(host, rule["domain_suffix"]):
            return rule["action"]
    return compiled["default"]


def parse_cidrs(text):
    """Strictly accept an IP-network file; reject mislabelled VPN subscription files."""
    networks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "://" in line:
            raise ValueError("Subscription URI is not a CIDR")
        try:
            network = ipaddress.ip_network(line, strict=False)
        except ValueError as exc:
            raise ValueError("Invalid CIDR input") from exc
        if network.prefixlen == 0 or not network.is_global:
            raise ValueError("Too broad or nonpublic network")
        networks.append(network)
    if not networks:
        raise ValueError("Empty CIDR list")
    result = []
    for family in (4, 6):
        result.extend(str(x) for x in ipaddress.collapse_addresses(
            n for n in networks if n.version == family))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="routing/policy.json")
    parser.add_argument("--out", default="routing/generated")
    args = parser.parse_args()
    config = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    result = compile_policy(config)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    (output / "rules.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for action in ("DIRECT", "PROXY", "BLOCK"):
        rows = [r["domain_suffix"] for r in result["rules"] if r["action"] == action]
        (output / (action.lower() + ".txt")).write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    (output / "review.txt").write_text("\n".join(result["review_candidates"]) + "\n", encoding="utf-8")
    print(json.dumps({"active_rules": len(result["rules"]), "review_only": len(result["review_candidates"]), "overrides": len(result["overrides"])}))


if __name__ == "__main__":
    main()
