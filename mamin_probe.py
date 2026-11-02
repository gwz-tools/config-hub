#!/usr/bin/env python3
"""Probe signed Mamin candidates THROUGH sing-box; emit only aggregate metrics.

No candidate URLs, credentials, or subscriptions are written to the repository.
A successful GitHub-runner probe is not proof of reachability on a mobile ISP.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from cloud_verified import SERVICE_URLS, test_candidate, unique_candidates


def probe(source, sing_box, max_candidates, workers):
    links = unique_candidates(source, max_candidates)
    if not links:
        raise ValueError("No parser-compatible VLESS candidates")
    passed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(test_candidate, link, sing_box) for link in links]
        for future in as_completed(futures):
            result = future.result()
            if result:
                passed.append(result)
    services = Counter()
    for result in passed:
        for name, status in result["statuses"].items():
            if 200 <= status < 400:
                services[name] += 1
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(links),
        "end_to_end_passed": len(passed),
        "services_2xx_3xx": {name: services[name] for name in SERVICE_URLS},
        "runner_note": "GitHub cloud probe only; not proof of access on Tele2/T2",
        "published": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--sing-box", default="sing-box")
    ap.add_argument("--max-candidates", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if not 1 <= args.max_candidates <= 100 or not 1 <= args.workers <= 8:
        ap.error("max-candidates must be 1..100 and workers 1..8")
    print(json.dumps(probe(args.source, args.sing_box, args.max_candidates, args.workers),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
