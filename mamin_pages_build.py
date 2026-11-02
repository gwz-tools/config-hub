#!/usr/bin/env python3
"""Build an unlisted Happ subscription for GitHub Pages from signed Mamin VLESS.

Security boundary:
* The input catalogue must verify against the key extracted from the exact
  pinned APK. No unverified or expired catalogue is ever used.
* VLESS links are never printed, committed or written to the checkout.
* Only successfully tested tunnels appear in the Pages upload artifact.
* If less than MIN_LIVE pass, fail WITHOUT uploading/deploying a new Pages site.
  Existing deployed Pages content remains unchanged.
* GitHub Pages and workflow artifacts are NOT private/authenticated storage:
  treat the long URL as obscurity, not authorization.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from cloud_verified import test_candidate, unique_candidates


PATH_RE = re.compile(r"^[a-f0-9]{48,64}$")


def validate_path(value: str) -> str:
    if not isinstance(value, str) or not PATH_RE.fullmatch(value):
        raise ValueError("MAMIN_PAGES_PATH must be 48-64 lowercase hex characters")
    return value


def verified_candidates(apk_file: Path, max_candidates: int) -> list[str]:
    """Run the already audited APK-pinned RS256 verifier without echoing secrets."""
    if not apk_file.is_file():
        raise RuntimeError("Pinned Mamin APK missing")
    with tempfile.TemporaryDirectory(prefix="mamin-pages-signed-") as tmp:
        root = Path(tmp)
        cmd = [
            sys.executable, str(Path(__file__).with_name("mamin_verify_import.py")),
            "--output-dir", str(root), "--apk-file", str(apk_file)
        ]
        try:
            verified = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=100
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("Signed catalogue verification failed") from None
        if verified.returncode:
            raise RuntimeError("Signed catalogue verification failed")
        # This file is generated ONLY after verifying signature, key ID,
        # schema, expiry and timestamps by mamin_verify_import.py.
        source = root / "mamin-vless-reality.verified.txt"
        candidates = unique_candidates(source, max_candidates)
        if not candidates:
            raise RuntimeError("Signed catalogue contains no compatible VLESS nodes")
        return candidates


def select_healthy(results: list[dict], min_live: int, max_live: int) -> list[str]:
    good = [
        x for x in results
        if isinstance(x, dict)
        and isinstance(x.get("line"), str)
        and x["line"].startswith("vless://")
        and int(x.get("functional", 0)) == 4
    ]
    good.sort(key=lambda x: float(x.get("latency", 99999)))
    unique = []
    seen = set()
    for result in good:
        link = result["line"]
        if link in seen:
            continue
        seen.add(link)
        unique.append(link)
        if len(unique) >= max_live:
            break
    if len(unique) < min_live:
        raise RuntimeError("Insufficient fully verified tunnels; deployment blocked")
    return unique


def verify_end_to_end(candidates: list[str], sing_box: str, workers: int) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(test_candidate, link, sing_box) for link in candidates]
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                # Never forward exception text; it can include a server or URI.
                continue
            if result is not None:
                results.append(result)
    return results


def write_site(output_dir: Path, secret_path: str, lines: list[str]) -> None:
    # Site content is public through an unlisted URL. Keep the URL itself out
    # of workflow logs, commit history, workflow summaries and public metadata.
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("Refusing to overwrite non-empty site staging directory")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    subscription_dir = output_dir / "sub" / secret_path
    subscription_dir.mkdir(parents=True, mode=0o700)
    target = subscription_dir / "mamin.txt"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)

    # No sitemap, no links to the subscription, no directory listing.
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n", encoding="utf-8"
    )
    (output_dir / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex,nofollow\">"
        "<title>Subscription host</title></head>"
        "<body><p>Subscription host.</p></body></html>\n",
        encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sing-box", default="sing-box")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--max-live", type=int, default=20)
    parser.add_argument("--min-live", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not (1 <= args.min_live <= args.max_live <= 100):
        parser.error("min-live/max-live outside allowed range")
    if not (1 <= args.max_candidates <= 100 and 1 <= args.workers <= 8):
        parser.error("max-candidates/workers outside allowed range")
    if not os.environ.get("RUNNER_TEMP"):
        parser.error("This publisher is intended for GitHub Actions only")
    try:
        secret = validate_path(os.environ.get("MAMIN_PAGES_PATH", ""))
    except ValueError:
        print("MAMIN_PAGES_PATH GitHub Actions secret missing/invalid", file=sys.stderr)
        return 2
    staging_base = Path(os.environ["RUNNER_TEMP"]).resolve()
    output = args.output_dir.resolve()
    if output == staging_base or staging_base not in output.parents:
        print("Refusing output outside the GitHub Actions runner temp directory",
              file=sys.stderr)
        return 2
    os.umask(0o077)
    try:
        candidates = verified_candidates(args.apk_file, args.max_candidates)
        good = verify_end_to_end(candidates, args.sing_box, args.workers)
        selected = select_healthy(good, args.min_live, args.max_live)
        write_site(output, secret, selected)
    except (RuntimeError, OSError, ValueError) as exc:
        # Only fixed categories, never URLs or credentials.
        print("Mamin subscription NOT deployed: signature/check/threshold failed",
              file=sys.stderr)
        return 2
    # Safe counters only. No full URL, path token, individual credentials.
    print(json.dumps({
        "status": "ready_to_deploy",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "rsa_verified_catalogue": True,
        "candidates_checked": len(candidates),
        "end_to_end_passed": len(good),
        "selected": len(selected),
        "minimum_required": args.min_live,
        "repository_commits_with_credentials": 0,
        "note": "Unlisted Pages URL is not access control; network-specific success not guaranteed",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
