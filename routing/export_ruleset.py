#!/usr/bin/env python3
"""Create sing-box/Podkop remote rule-set JSON from staged domain policy.

Rule-sets contain matches ONLY, not DNS / outbound decisions. The importing
Podkop section (Exclusion, Proxy or Block) chooses the action. No full client
configuration is imported or generated here.
"""
import argparse
import json
from pathlib import Path
from build import compile_policy


def ruleset_for(compiled, route):
    rows = sorted({r["domain_suffix"] for r in compiled["rules"]
                   if r["action"] == route})
    return {"version": 3, "rules": [{"domain_suffix": rows}] if rows else []}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--policy", type=Path, default=Path("routing/policy.json"))
    cli.add_argument("--output", type=Path, default=Path("/tmp/gwz-ruleset"))
    cli.add_argument("--validated-legacy", type=Path, default=None,
                     help="Required to generate deployment-eligible DIRECT: exact multi-router comparison JSON")
    args = cli.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if args.validated_legacy:
        data = json.loads(args.validated_legacy.read_text(encoding="utf-8"))
        if data.get("kind") != "podkop_EXCLUSION_direct_domains" or data.get("requires_review"):
            cli.error("Legacy sources differ or missing; cannot generate deployment-eligible DIRECT list")
        legacy = data["common"]
        if len(legacy) < 50:
            cli.error("Legacy export suspiciously small; refusing promotion")
        # Exact observed existing rules are authoritative. Do not accidentally remove any.
        policy["direct_domains"] = sorted(set(policy.get("direct_domains", [])) | set(legacy))
    compiled = compile_policy(policy)
    args.output.mkdir(parents=True, exist_ok=True)
    for route in ("DIRECT", "PROXY", "BLOCK"):
        ruleset = ruleset_for(compiled, route)
        name = route.lower() + "-domains.rule-set.json"
        (args.output / name).write_text(json.dumps(ruleset, ensure_ascii=False,
                                                  sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {"deployment_eligible": bool(args.validated_legacy),
               "direct": sum(r["action"] == "DIRECT" for r in compiled["rules"]),
               "proxy": sum(r["action"] == "PROXY" for r in compiled["rules"]),
               "block": sum(r["action"] == "BLOCK" for r in compiled["rules"]),
               "conflicts": len(compiled["overrides"]),
               "note": "Rule-set files do not set routing action; use correct Podkop section."}
    (args.output / "build-report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
