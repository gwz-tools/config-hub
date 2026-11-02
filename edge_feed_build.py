#!/usr/bin/env python3
"""Build an unlisted, periodically refreshed VLESS feed in an Actions temp directory.

Never logs or commits a credential in the source checkout. A separate workflow
may publish the verified output to a random unlisted path in the published
branch. This path is public to repository browsers: not true authentication.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import quote

from cloud_verified import test_candidate, unique_candidates


def source_candidates(apk: Path, limit: int) -> list[str]:
    """Verify a fresh signed catalogue against the pinned key from the pinned APK."""
    if not apk.is_file():
        raise RuntimeError("Pinned source APK missing")
    with tempfile.TemporaryDirectory(prefix="edge-signed-source-") as td:
        out = Path(td)
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("mamin_verify_import.py")),
             "--apk-file", str(apk), "--output-dir", str(out)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=100, check=False,
        )
        if proc.returncode:
            raise RuntimeError("Signature, freshness or schema check failed")
        candidates = unique_candidates(out / "mamin-vless-reality.verified.txt", limit)
        if not candidates:
            raise RuntimeError("No compatible signed candidates")
        return candidates


def select(results: list[dict], minimum: int, maximum: int) -> list[str]:
    valid = []
    seen = set()
    ordered = sorted(
        (x for x in results
         if isinstance(x, dict)
         and isinstance(x.get("line"), str)
         and x["line"].startswith("vless://")
         and x.get("functional") == 4),
        key=lambda x: float(x.get("latency", 999999)),
    )
    for item in ordered:
        base = item["line"].split("#", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        # Hide original upstream remarks, not credentials/protocol parameters.
        # The URI may still contain an identifying hostname: never modify it.
        valid.append(base + "#"+quote(f"Relay {len(valid) + 1:02d}", safe=""))
        if len(valid) == maximum:
            break
    if len(valid) < minimum:
        raise RuntimeError("Healthy candidate threshold not met")
    return valid


def test_all(candidates: list[str], binary: str, workers: int) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(test_candidate, x, binary) for x in candidates]
        for f in as_completed(futures):
            try:
                value = f.result()
            except Exception:
                # Exceptions may contain sensitive remote endpoints.
                continue
            if value is not None:
                results.append(value)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sing-box", default="sing-box")
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--min-live", type=int, default=3)
    parser.add_argument("--max-live", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not (1 <= args.min_live <= args.max_live <= 100):
        parser.error("Invalid min/max")
    if not (1 <= args.candidates <= 100 and 1 <= args.workers <= 8):
        parser.error("Invalid test limits")
    runner_temp = os.environ.get("RUNNER_TEMP", "")
    if not runner_temp:
        parser.error("Only for the private staging area of a GitHub runner")
    out = args.output.resolve()
    if Path(runner_temp).resolve() not in out.parents:
        parser.error("Output must be within RUNNER_TEMP")
    os.umask(0o077)
    try:
        candidates = source_candidates(args.apk, args.candidates)
        tested = test_all(candidates, args.sing_box, args.workers)
        selected = select(tested, args.min_live, args.max_live)
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError):
        # Never echo raw exception, possibly containing credentials.
        print("No valid update: signature, transport or minimum-health guard failed",
              file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    # Standard URL subscription format supported by Happ, no brand attribution.
    content = (
        "# profile-title: Relay / VLESS\n"
        "# profile-update-interval: 6\n"
        + "\n".join(selected) + "\n"
    )
    with out.open("x", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(content)
    print(json.dumps({
        "status": "ready",
        "signed_catalogue": True,
        "tested": len(candidates),
        "passed": len(tested),
        "selected": len(selected),
        "published": False,
        "note": "Cloud validation is not proof of access from each device/network",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
