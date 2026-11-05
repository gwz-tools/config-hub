#!/usr/bin/env python3
"""Compare candidate public VLESS subscription sources against existing GWZHUB.

Never log VLESS URLs or passwords. Only report aggregate distinct compatible
connection identities and counts. A compatible URL has a valid sing-box VLESS
transport, not evidence of a reachable server.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request, urlopen

from cloud_verified import parse_vless

MAX_SOURCE = 8 * 1024 * 1024
VLESS = re.compile(r"vless://[^\s<>\"']+")


def identity(url):
    url = url.strip().split("#", 1)[0]
    try:
        info = urlsplit(url)
        if info.scheme != "vless" or not info.hostname or not info.port:
            return None
        parse_vless(url)
        return (info.hostname.lower(), info.port, info.username,
                tuple(sorted(parse_qsl(info.query, keep_blank_values=True))))
    except (ValueError, TypeError):
        return None


def extract(text):
    raw = VLESS.findall(text)
    if raw:
        return raw
    candidate = "".join(text.split())
    if re.fullmatch(r"[a-zA-Z0-9+/=_-]+", candidate or "") and len(candidate) < MAX_SOURCE:
        try:
            content = base64.urlsafe_b64decode(candidate + "=" * (-len(candidate) % 4)).decode("utf-8", "ignore")
            return VLESS.findall(content)
        except ValueError:
            pass
    return []


def download(url):
    with urlopen(Request(url, headers={"User-Agent": "GWZHUB-source-research/1.0"}),
                 timeout=16) as resp:
        if resp.status != 200:
            raise ValueError("non-200")
        raw = resp.read(MAX_SOURCE + 1)
        if len(raw) > MAX_SOURCE:
            raise ValueError("large feed over 8 MiB")
        return raw.decode("utf-8", "replace")


def main():
    original = Path("data/validated.txt").read_text(encoding="utf-8", errors="ignore")
    baseline = set(filter(None, map(identity, VLESS.findall(original))))
    seen = set(baseline)
    print("BASELINE", len(baseline), flush=True)
    for item in Path("source_incremental_urls.txt").read_text().splitlines():
        if not item.strip() or item.startswith("#"):
            continue
        name, url = item.split(" ", 1)
        try:
            items = set(filter(None, map(identity, extract(download(url)))))
            incremental = items - seen
            unseen = items - baseline
            seen.update(items)
            record = {"name": name, "compatible": len(items), "new_vs_existing": len(unseen),
                      "additional_unique": len(incremental), "status": "ok"}
        except Exception as exc:
            record = {"name": name, "compatible": 0, "new_vs_existing": 0,
                      "additional_unique": 0, "status": type(exc).__name__}
        print("INCREMENTAL_JSON "+json.dumps(record, separators=(",",":")), flush=True)


if __name__ == "__main__":
    main()
