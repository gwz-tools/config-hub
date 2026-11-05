#!/usr/bin/env python3
"""Publish a validated whole routing snapshot to a dedicated Git branch.

Intended ONLY for the manually dispatched GitHub Action after merge to main.
This tool never mutates VLESS subscription files, Podkop, or running routers.
Uses a single git commit for manifest and six sibling assets.
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ASSETS = (
    "manifest.json",
    "direct.txt",
    "proxy.txt",
    "block.txt",
    "direct.rule-set.json",
    "proxy.rule-set.json",
    "block.rule-set.json",
)
BRANCH = "routing-feed"


def run(*args, cwd, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()

    from publish_bundle import verify_bundle
    import json

    src = opts.bundle.resolve(strict=True)
    items = {key: (src / key).read_bytes() for key in ASSETS}
    manifest = json.loads(items["manifest.json"])
    verify_bundle({k: v for k, v in items.items() if k != "manifest.json"}, manifest)
    version = manifest["version"]

    # Normal GitHub Actions checks out one branch; keep the source checkout intact.
    with tempfile.TemporaryDirectory(prefix="gwzhub-routing-release-") as td:
        staging = Path(td)
        run("git", "init", "-q", cwd=staging)
        url = run("git", "remote", "get-url", opts.remote, cwd=Path.cwd()).stdout.strip()
        if not url:
            raise RuntimeError("Cannot identify authenticated repository remote")
        token = os.getenv("GITHUB_TOKEN")
        repo = os.getenv("GITHUB_REPOSITORY")
        if token and repo:
            # Dedicated temporary checkout; credential is not committed or logged.
            url = "https://x-access-token:" + token + "@github.com/" + repo + ".git"
        elif not opts.dry_run:
            raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY required for publish")
        run("git", "remote", "add", "origin", url, cwd=staging)
        found = run("git", "ls-remote", "--heads", "origin", BRANCH, cwd=staging).stdout.strip()
        if found:
            run("git", "fetch", "-q", "--depth=1", "origin", BRANCH, cwd=staging)
            run("git", "checkout", "-q", "-B", BRANCH, "FETCH_HEAD", cwd=staging)
        else:
            run("git", "checkout", "-q", "--orphan", BRANCH, cwd=staging)
        for key in ASSETS:
            (staging / key).write_bytes(items[key])
        (staging / "README.md").write_text(
            "GWZHUB routing feed: generated files only.\n\n"
            "Do not edit here: change routing/confirmed-{direct,proxy}-20261105.txt on main.\n"
            "The manifest and its assets are pushed together in one Git commit.\n"
            "Clients must verify all SHA256 before activation and retain last known good.\n",
            encoding="utf-8")
        run("git", "add", "--", *ASSETS, "README.md", cwd=staging)
        changes = run("git", "diff", "--cached", "--quiet", cwd=staging, check=False)
        if changes.returncode == 0:
            print("Routing feed unchanged: " + version)
            return
        run("git", "-c", "user.name=gwzhub-routing-bot",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-q", "-m", "Publish GWZHUB routing policy " + version, cwd=staging)
        if opts.dry_run:
            print("DRY-RUN: would publish " + version)
            return
        # Never force-push: conflicting simultaneous writers must fail and retry.
        run("git", "push", "origin", "HEAD:refs/heads/" + BRANCH, cwd=staging)
        print("Published GWZHUB routing policy: " + version)


if __name__ == "__main__":
    main()
