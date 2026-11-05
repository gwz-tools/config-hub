#!/usr/bin/env python3
"""Compile the explicitly confirmed DIRECT / VPN policy (staging only).

Strong policy inputs come from operator-supplied lists, and are not silently mixed
with review-only candidates. Changes neither install router config nor modify feeds.
"""
import argparse
import json
from pathlib import Path
from build import compile_policy, domain, matches


def read_domains(file):
    values = []
    for line in Path(file).read_text(encoding="utf-8-sig").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        values.append(domain(raw))
    if not values:
        raise ValueError("Empty confirmed domain list: " + str(file))
    return sorted(set(values))


def compile_confirmed(direct, proxy):
    direct_set = set(direct)
    proxy_set = set(proxy)
    exact = sorted(direct_set & proxy_set)
    # An apex DIRECT suffix might otherwise absorb a specifically named VPN service.
    # Until explicitly reviewed, ALL cross-action overlaps are a hard error.
    overlap = sorted((d, p) for d in direct_set for p in proxy_set
                     if matches(d, p) or matches(p, d))
    if exact or overlap:
        raise ValueError("DIRECT/PROXY conflicts: " +
                         json.dumps({"exact": exact, "suffix": overlap[:50]}))
    base = {"schema_version": 1, "default_public_route": "PROXY",
            "direct_domains": sorted(direct_set),
            "proxy_domains": sorted(proxy_set),
            "block_domains": [],
            "review_direct_candidates": []}
    return compile_policy(base)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", type=Path, default=Path("routing/confirmed-direct-20261105.txt"))
    parser.add_argument("--proxy", type=Path, default=Path("routing/confirmed-proxy-20261105.txt"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/gwzhub-confirmed-policy"))
    opts = parser.parse_args()
    direct, proxy = read_domains(opts.direct), read_domains(opts.proxy)
    result = compile_confirmed(direct, proxy)
    opts.output.mkdir(parents=True, exist_ok=True)
    (opts.output / "rules.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    for route in ("DIRECT", "PROXY", "BLOCK"):
        rows = [r["domain_suffix"] for r in result["rules"] if r["action"] == route]
        (opts.output / (route.lower() + ".txt")).write_text(
            "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        rule_set = {"version": 3, "rules": [{"domain_suffix": rows}] if rows else []}
        (opts.output / (route.lower() + ".rule-set.json")).write_text(
            json.dumps(rule_set, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"direct": len(direct), "proxy": len(proxy),
              "exact_conflicts": 0, "suffix_conflicts": 0,
              "production_deployed": False,
              "note": "No VPN-down kill-switch guaranteed by these domain-only matches."}
    (opts.output / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                              encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
