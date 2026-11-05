#!/usr/bin/env python3
"""Import *sanitized* Podkop exclusion domain lists (never upload full UCI).

Source input is exact text returned by:
  uci -q get podkop.ru_apps.user_domains_text
This tool never edits routers, makes assumptions about historic counts, or merges
conflicting lists silently.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from build import domain

# Keep credentials and generic UCI directives out of the domain export.
SAFE_LINE = re.compile(r"^[a-zA-Z0-9*_.-]+$")


def parse_domains(text):
    found = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        clean = raw.split("//", 1)[0].split("#", 1)[0].strip()
        if not clean:
            continue
        for item in re.split(r"[\s,;]+", clean):
            if not item:
                continue
            if not SAFE_LINE.fullmatch(item):
                raise ValueError(f"Unsupported item on line {lineno}: refusing credentials or UCI dump")
            found.add(domain(item))
    if not found:
        raise ValueError("Empty domain export")
    return sorted(found)


def inspect_exports(named_texts):
    if len(named_texts) < 1:
        raise ValueError("At least one source export required")
    parsed = {name: parse_domains(text) for name, text in named_texts.items()}
    names = sorted(parsed)
    union = sorted(set().union(*(set(domains) for domains in parsed.values())))
    shared = sorted(set.intersection(*(set(v) for v in parsed.values())))
    discrepancies = {
        name: sorted(set(union) - set(parsed[name])) for name in names
    }
    return {
        "schema_version": 1,
        "kind": "podkop_EXCLUSION_direct_domains",
        "sources": {
            name: {
                "count": len(parsed[name]),
                "sha256": hashlib.sha256(("\n".join(parsed[name]) + "\n").encode()).hexdigest(),
                "domains": parsed[name],
            } for name in names
        },
        "union": union,
        "common": shared,
        "missing_by_source": discrepancies,
        "requires_review": len(names) < 2 or any(discrepancies.values()),
        "note": "Sources are independent observations, never auto-write these into main/Podkop.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", nargs="+", metavar="NAME=FILE", required=True)
    parser.add_argument("--output", type=Path, default=Path("/tmp/gwz-direct-audit.json"))
    args = parser.parse_args()
    files = {}
    for entry in args.source:
        name, sep, path = entry.partition("=")
        if not sep or not re.fullmatch(r"[a-z0-9_-]{2,30}", name) or name in files:
            parser.error("Provide unique NAME=FILE for each source")
        files[name] = Path(path).read_text(encoding="utf-8")
    report = inspect_exports(files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"counts": {n: p["count"] for n, p in report["sources"].items()},
                      "union": len(report["union"]), "common": len(report["common"]),
                      "requires_review": report["requires_review"]}))


if __name__ == "__main__":
    main()
