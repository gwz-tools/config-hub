#!/usr/bin/env python3
"""Reference routing-feed updater for GWZHUB.

No operating-system VPN or Podkop changes. Download bundle, verify it, then
persist an atomic local snapshot. Android implementation may use same contract.
"""
import argparse
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from publish_bundle import verify_bundle

ASSETS = (
    "direct.txt", "proxy.txt", "block.txt",
    "direct.rule-set.json", "proxy.rule-set.json", "block.rule-set.json",
)
MAX_MANIFEST_BYTES = 64 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 6 * 1024 * 1024
MAX_VERSIONS = 3
VERSION_PATTERN = re.compile(r"^[a-f0-9]{20}$")


class UpdateFailed(RuntimeError):
    pass


def _read_limited(response, max_bytes):
    data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UpdateFailed("download size exceeded")
    return data


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise UpdateFailed("redirect not allowed for trusted policy feed")


def fetch_https(url, etag=None, *, timeout=8, opener=None, limit=MAX_FILE_BYTES):
    u = urllib.parse.urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.port not in (None, 443)
            or u.username or u.password or u.query or u.fragment):
        raise UpdateFailed("Untrusted feed URL")
    client = opener or urllib.request.build_opener(NoRedirect())
    headers = {"Accept": "application/json,text/plain;q=0.8", "User-Agent": "GWZHUB-policy-client/1"}
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with client.open(request, timeout=timeout) as response:
            return response.status, _read_limited(response, limit), response.headers.get("ETag")
    except urllib.error.HTTPError as err:
        if err.code == 304:
            return 304, b"", etag
        raise UpdateFailed("HTTP status " + str(err.code)) from err
    except (OSError, ValueError) as err:
        raise UpdateFailed("Policy feed unavailable") from err


def feed_url_parts(manifest_url):
    url = urllib.parse.urlsplit(manifest_url)
    if (url.scheme != "https" or url.username or url.password
            or url.port not in (None, 443) or url.query or url.fragment
            or not url.hostname or not url.path.endswith("/manifest.json")):
        raise UpdateFailed("Invalid manifest URL")
    return manifest_url.rsplit("/", 1)[0] + "/"


def read_active(cache_dir):
    current = cache_dir / "current.json"
    try:
        version = json.loads(current.read_text(encoding="utf-8"))["version"]
        if not VERSION_PATTERN.fullmatch(version):
            return None
        bundle_dir = cache_dir / "versions" / version
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        files = {name: (bundle_dir / name).read_bytes() for name in ASSETS}
        verify_bundle(files, manifest)
        return version, files, manifest
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def atomic_write(path, content):
    fd, temp = tempfile.mkstemp(prefix=".gwzhub-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def update(cache_dir, manifest_url, fetch=fetch_https):
    """Return 'updated' or 'unchanged'. Any error leaves active snapshot unchanged."""
    cache_dir = Path(cache_dir)
    base = feed_url_parts(manifest_url)
    old = read_active(cache_dir)
    # Fetch with ETag only when cached files and manifest are fully verified.
    old_etag = None
    etag_path = cache_dir / "etag.txt"
    if old and etag_path.exists():
        old_etag = etag_path.read_text(encoding="utf-8").strip()
    status, manifest_data, new_etag = fetch(manifest_url, old_etag, limit=MAX_MANIFEST_BYTES)
    if status == 304:
        if not old:
            raise UpdateFailed("304 without verified local policy")
        return "unchanged"
    if status != 200:
        raise UpdateFailed("Unexpected manifest response")
    try:
        manifest = json.loads(manifest_data)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise ValueError("unsupported manifest")
        version = manifest.get("version")
        if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
            raise ValueError("unsafe version")
        if set(manifest.get("files", {})) != set(ASSETS):
            raise ValueError("missing or extraneous assets")
        expected = sum(v["bytes"] for v in manifest["files"].values())
        if (expected > MAX_TOTAL_BYTES or expected < 0 or
                any(type(v["bytes"]) is not int or v["bytes"] < 0 or
                    v["bytes"] > MAX_FILE_BYTES for v in manifest["files"].values())):
            raise ValueError("asset sizes exceed policy")
    except (ValueError, KeyError, TypeError) as exc:
        raise UpdateFailed("Invalid routing manifest") from exc

    if old and old[0] == version:
        return "unchanged"
    files = {}
    for name in ASSETS:
        status, content, _ = fetch(base + name, limit=MAX_FILE_BYTES)
        if status != 200:
            raise UpdateFailed("Incomplete routing bundle")
        files[name] = content
    try:
        verify_bundle(files, manifest)
    except (ValueError, KeyError, TypeError) as err:
        raise UpdateFailed("Routing verification failed") from err

    # Write entire version before replacing active pointer. Save previous
    # version for rollback. Atomic file replacement must share filesystem.
    versions = cache_dir / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    folder = versions / version
    if not folder.exists():
        temp_dir = Path(tempfile.mkdtemp(prefix=".staging-", dir=versions))
        try:
            for name, content in files.items():
                (temp_dir / name).write_bytes(content)
            (temp_dir / "manifest.json").write_bytes(manifest_data)
            temp_dir.rename(folder)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
    atomic_write(cache_dir / "current.json", json.dumps({"version": version}).encode())
    if new_etag:
        atomic_write(etag_path, new_etag.encode())
    elif etag_path.exists():
        etag_path.unlink()
    # Keep active and previous successfully verified versions; avoid aggressive
    # eviction until a separate rollback policy is implemented.
    return "updated"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--manifest", required=True)
    opts = parser.parse_args()
    try:
        print(update(opts.cache, opts.manifest))
    except UpdateFailed as exc:
        if read_active(opts.cache):
            print("Kept last-known-good policy: " + str(exc))
            return
        raise SystemExit("No verified local policy: " + str(exc))


if __name__ == "__main__":
    main()
