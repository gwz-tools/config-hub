#!/usr/bin/env python3
"""Private, fail-closed Mamin VPN source for GWZHUB.

Signed catalogue -> APK-pinned RS256 -> isolated sing-box HTTPS checks
-> atomic private last-good feed. Never publishes credentials to GitHub.
No changes to router, Podkop, existing subscriptions, or GWZHUB database.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from cloud_verified import test_candidate, unique_candidates

ROOT_DEFAULT = Path("/opt/gwzhub/data/mamin")
PRIVATE_FEED = "mamin-private-live.txt"
STATUS_FILE = "status.json"
SEQUENCE_FILE = "mamin-catalogue-sequence.json"


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mamin-write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def last_good_count(root: Path) -> int:
    file = root / PRIVATE_FEED
    if not file.exists():
        return 0
    return sum(line.startswith("vless://") for line in file.read_text(encoding="utf-8").splitlines())


def status_base(root: Path) -> dict:
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "mamin-bootstrap-v2",
        "signature_verified": False,
        "candidates_tested": 0,
        "end_to_end_passed": 0,
        "last_good_count": last_good_count(root),
        "feed_updated": False,
        "published_to_public_github": False,
        "scope": "private_gwzhub_only",
        "note": "Hub-side checks do not guarantee access via Tele2/T2",
    }


def probe_candidates(candidates: list[str], sing_box: str, workers: int) -> list[dict]:
    """Use the EXISTING cloud checker: genuine HTTPS through each VLESS tunnel."""
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(test_candidate, url, sing_box) for url in candidates]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    return results


def promote(root: Path, staged_sequence: Path, results: list[dict],
            min_live: int, max_live: int) -> int:
    """Replace ONLY private Mamin last-good; refuse zero/under-threshold feeds."""
    good = [r for r in results if isinstance(r, dict) and
            isinstance(r.get("line"), str) and r["line"].startswith("vless://")]
    previous_count = last_good_count(root)
    # Hysteresis: do not halve the size of a previously healthy source overnight.
    required = max(min_live, (previous_count + 1) // 2)
    if len(good) < required:
        raise ValueError(f"Only {len(good)} of {required} required verified tunnels")
    if not staged_sequence.is_file():
        raise ValueError("Missing signed catalogue sequence state")
    signed_state = json.loads(staged_sequence.read_text(encoding="utf-8"))
    if not isinstance(signed_state.get("sequence"), int) or isinstance(signed_state.get("sequence"), bool):
        raise ValueError("Invalid signed catalogue sequence state")
    good.sort(key=lambda r: (-int(r.get("functional", 0)), float(r.get("latency", 9999))))
    selected = []
    seen = set()
    for result in good:
        link = result["line"]
        if link not in seen:
            seen.add(link)
            selected.append(link)
        if len(selected) >= max_live:
            break
    if len(selected) < min_live:
        raise ValueError("Too few unique verified tunnels")
    atomic_write(root / PRIVATE_FEED, ("\n".join(selected) + "\n").encode("utf-8"))
    atomic_write(root / SEQUENCE_FILE, staged_sequence.read_bytes())
    return len(selected)


def run(args: argparse.Namespace) -> int:
    os.umask(0o077)
    root = args.data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    lock_file = root / ".update.lock"
    with lock_file.open("a+") as lock:
        os.chmod(lock_file, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Mamin audit already in progress; no changes")
            return 3

        status = status_base(root)
        try:
            with tempfile.TemporaryDirectory(prefix=".staging-", dir=root) as td:
                stage = Path(td)
                old = root / SEQUENCE_FILE
                if old.is_file():
                    shutil.copyfile(old, stage / SEQUENCE_FILE)
                    os.chmod(stage / SEQUENCE_FILE, 0o600)
                importer = Path(__file__).resolve().with_name("mamin_verify_import.py")
                cmd = [sys.executable, str(importer), "--output-dir", str(stage),
                       "--apk-file", str(args.apk_file)]
                if args.catalog_file is not None:
                    cmd.extend(["--catalog-file", str(args.catalog_file)])
                checked = subprocess.run(cmd, capture_output=True, text=True,
                                         timeout=100, check=False)
                if checked.returncode:
                    raise RuntimeError("Catalogue signature, expiry or sequence verification failed")
                status["signature_verified"] = True

                source = stage / "mamin-vless-reality.verified.txt"
                candidates = unique_candidates(source, args.max_candidates)
                if not candidates:
                    raise RuntimeError("No compatible VLESS Reality candidates")
                status["candidates_tested"] = len(candidates)
                if not shutil.which(args.sing_box):
                    raise RuntimeError("Isolated sing-box binary is missing or not executable")
                results = probe_candidates(candidates, args.sing_box, args.workers)
                status["end_to_end_passed"] = len(results)
                status["pass_rate_pct"] = round(100 * len(results) / len(candidates), 1)
                count = promote(root, stage / SEQUENCE_FILE, results,
                                args.min_live, args.max_live)
                status["last_good_count"] = count
                status["feed_updated"] = True
                status["status"] = "healthy"
                atomic_write(root / STATUS_FILE, (json.dumps(status, indent=2) + "\n").encode())
                print(json.dumps(status, ensure_ascii=False))
                return 0
        except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            # Deliberately do NOT log untrusted source URLs, catalogues or credentials.
            status["status"] = "retained_last_good"
            status["reason"] = type(exc).__name__
            status["last_good_count"] = last_good_count(root)
            atomic_write(root / STATUS_FILE, (json.dumps(status, indent=2) + "\n").encode())
            print(json.dumps(status, ensure_ascii=False), file=sys.stderr)
            return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Mamin private GWZHUB source updater")
    parser.add_argument("--apk-file", type=Path, required=True,
                        help="The exact SHA256-pinned Mamin-VPN-0.9.29.apk")
    parser.add_argument("--catalog-file", type=Path, help="Offline signed test catalogue")
    parser.add_argument("--data-dir", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--sing-box", default=str(Path(__file__).resolve().parent / "bin" / "sing-box"),
                        help="Isolated sing-box installed beside the Mamin updater")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--max-live", type=int, default=20)
    parser.add_argument("--min-live", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.max_candidates <= 100:
        parser.error("--max-candidates must be 1..100")
    if not 1 <= args.max_live <= 100:
        parser.error("--max-live must be 1..100")
    if not 1 <= args.min_live <= args.max_live:
        parser.error("--min-live must be 1..max-live")
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be 1..8")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
