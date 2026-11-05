#!/usr/bin/env python3
"""Audit public GWZHUB source URLs by actual HTTPS response and sampled content.

This is NOT a tunnel validator: a functioning source does not imply its VPN
endpoints will work. Read no more than 384 KiB per address. Never print nodes.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LIMIT = 384 * 1024
TIMEOUT = 15
RE_VLESS = re.compile(r"vless://[^\s<>'\"\\]+", re.I)
RE_PROXY = re.compile(r"(?:ss|trojan|vmess|hysteria2?)://", re.I)
RE_CIDR = re.compile(r"(?m)^\s*(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}\s*$")


def decode_b64(text):
    s = "".join(text.split())
    if len(s) < 24 or len(s) > LIMIT * 1.4 or not re.fullmatch(r"[a-zA-Z0-9+/=_-]+", s):
        return ""
    try:
        data = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        return data.decode("utf-8", errors="replace")[:LIMIT]
    except (ValueError, UnicodeError):
        return ""


def classify(text, content_type, url):
    low = text[:1200].lower()
    if "<html" in low or "<!doctype html" in low or "text/html" in content_type.lower():
        return "HTML_OR_SITE", 0
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            if "outbounds" in obj or "proxies" in obj:
                return "JSON_VPN_CONFIGURATION", 0
            if "items" in obj and "total_count" in obj:
                return "JSON_SEARCH_API_NOT_FEED", 0
            if any(x in obj for x in ("sources", "urls", "subscriptions")):
                return "JSON_SOURCE_REGISTRY_NOT_FEED", 0
            return "JSON_OTHER_NOT_FEED", 0
        if isinstance(obj, list):
            return "JSON_LIST_NOT_DIRECT_FEED", 0
    except (ValueError, TypeError):
        pass
    count = len(RE_VLESS.findall(text))
    if count:
        return "VLESS_FEED", count
    decoded = decode_b64(text)
    if decoded:
        count = len(RE_VLESS.findall(decoded))
        if count:
            return "BASE64_VLESS_FEED", count
        if RE_PROXY.search(decoded):
            return "BASE64_OTHER_PROXY", 0
    if RE_PROXY.search(text):
        return "OTHER_PROXY_FEED", 0
    if len(RE_CIDR.findall(text)) >= 3 or ("cidr" in url.lower() and len(text.splitlines())>5):
        return "CIDR_RULES_NOT_VPN", 0
    if ("white-sni" in url.lower() or "white-list" in url.lower() or
        "whitelist" in url.lower()) and len(text.splitlines()) > 3:
        return "DOMAIN_RULES_NOT_VPN", 0
    if text.strip().startswith(("https://", "http://")):
        return "URL_INDEX_NOT_VPN", 0
    if not text.strip():
        return "EMPTY", 0
    return "OTHER_TEXT_NOT_VPN", 0


def audit(index, url):
    res = {"id": index, "url": url, "http": 0, "kind": "ERROR",
           "vless_sample": 0, "sample_bytes": 0, "truncated": False, "error": ""}
    try:
        if urlparse(url).scheme != "https":
            raise ValueError("Only https permitted")
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 GWZHUB-Source-Audit/1.0",
                                    "Accept": "text/plain,application/json,*/*",
                                    "Cache-Control": "no-cache"})
        with urlopen(req, timeout=TIMEOUT) as response:
            res["http"] = response.status
            payload = response.read(LIMIT + 1)
            res["truncated"] = len(payload) > LIMIT
            payload = payload[:LIMIT]
            res["sample_bytes"] = len(payload)
            res["kind"], res["vless_sample"] = classify(
                payload.decode("utf-8", errors="replace"),
                response.headers.get("Content-Type", ""), url)
    except HTTPError as exc:
        res["http"] = exc.code
        res["kind"] = "HTTP_ERROR"
    except (URLError, OSError, TimeoutError, ValueError) as exc:
        res["kind"] = "NETWORK_ERROR"
        res["error"] = type(exc).__name__
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    tasks = []
    for file in args.files:
        for url in file.read_text(encoding="utf-8").splitlines():
            if url.strip() and not url.lstrip().startswith("#"):
                tasks.append((len(tasks)+1, url.strip()))
    print("AUDIT_INPUT_COUNT", len(tasks), flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, 8))) as executor:
        pending = [executor.submit(audit, index, url) for index, url in tasks]
        for f in as_completed(pending):
            results.append(f.result())
    for item in sorted(results, key=lambda x:x["id"]):
        print("AUDIT_JSON " + json.dumps(item, ensure_ascii=False, separators=(",",":")), flush=True)
    from collections import Counter
    print("AUDIT_SUMMARY " + json.dumps({
        "total": len(results),
        "by_kind": dict(Counter(x["kind"] for x in results)),
        "http_200": sum(x["http"] == 200 for x in results),
        "candidate_feeds": sum(x["kind"] in ("VLESS_FEED","BASE64_VLESS_FEED") for x in results)
    }, ensure_ascii=False, separators=(",",":")), flush=True)


if __name__ == "__main__":
    main()
