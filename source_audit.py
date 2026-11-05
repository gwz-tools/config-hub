#!/usr/bin/env python3
"""Audit URLs for usable VLESS content. Do not fetch nested URLs or publish credentials."""
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CATALOG = Path("source_catalog.txt")
JSON_OUT = Path("data/source_audit.json")
TEXT_OUT = Path("data/source_audit_report.txt")
ALLOWED = {"github.com", "raw.githubusercontent.com", "gitlab.com", "codeberg.org",
           "cdn.jsdelivr.net", "api.github.com", "gitverse.ru", "warp-gen.cyb-portal.org",
           "alexandrovu96-stack.github.io", "mamin-starter-catalogue.surge.sh",
           "maminvpn-files.surge.sh"}
MAX_BYTES = 5_000_000


def approved(url):
    p = urlparse(url)
    return p.scheme == "https" and p.hostname in ALLOWED and not p.username and not p.password


def valid_links(lines):
    urls = {line.strip().split("#", 1)[0] for line in lines
            if line.strip().startswith("vless://")}
    if urls:
        return len(urls), hashlib.sha256("\n".join(sorted(urls)).encode()).hexdigest()[:16]
    return 0, None


def describe(url, content, content_type=""):
    value = content.decode("utf-8", "replace").strip()
    if not value:
        return "empty", 0, None
    if value.lower().startswith(("<!doctype html", "<html", "<head")) or "text/html" in content_type:
        return "webpage_not_feed", 0, None
    if any(x in url.lower() for x in ["white-sni-", "white-cidr-", "kirya", "/white-lists/"]):
        return "routing_rules", 0, None
    if url.endswith("sources.txt") or url.endswith("/urls.json"):
        return "source_index_not_feed", 0, None
    if url.endswith("singbox.json"):
        try:
            data = json.loads(value)
            def count(obj):
                if isinstance(obj, dict):
                    return int(obj.get("type") == "vless") + sum(count(v) for v in obj.values())
                if isinstance(obj, list):
                    return sum(count(v) for v in obj)
                return 0
            return "singbox_json", count(data), None
        except (ValueError, RecursionError):
            return "invalid_json", 0, None
    if value.startswith(("{", "[")):
        try:
            json.loads(value)
            return "json_not_subscription", 0, None
        except ValueError:
            return "invalid_json", 0, None
    n, sig = valid_links(value.splitlines())
    if n:
        return "vless_text", n, sig
    compact = "".join(value.split())
    if len(compact) >= 40 and re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
        try:
            decoded = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=True)
            n, sig = valid_links(decoded.decode("utf-8", "replace").splitlines())
            if n:
                return "vless_base64", n, sig
        except ValueError:
            pass
    return "other_text_not_vless", 0, None


def inspect(url):
    out = {"url": url, "status": "unknown", "kind": "unknown", "vless": 0}
    if not approved(url):
        return dict(out, status="unsupported_url")
    parsed = urlparse(url)
    if parsed.path in {"", "/"} or (parsed.hostname == "github.com" and "/raw/" not in parsed.path):
        return dict(out, status="not_feed", kind="repository_or_landing_page")
    if parsed.hostname == "api.github.com" and parsed.path.startswith("/search/"):
        return dict(out, status="not_feed", kind="discovery_api_not_subscription")
    try:
        request = Request(url, headers={"User-Agent": "GWZHUB-Source-Audit/1.0"})
        with urlopen(request, timeout=12) as response:
            if not approved(response.url):
                return dict(out, status="redirect_to_unapproved_host")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                return dict(out, status="too_large", kind="content_exceeds_5MB")
            kind, count, digest = describe(url, body, response.headers.get("Content-Type", "").lower())
            out.update(status="ok", kind=kind, vless=count, bytes=len(body))
            if digest:
                out["content_fingerprint"] = digest
    except HTTPError as error:
        out.update(status="http_" + str(error.code), kind="http_error")
    except (URLError, TimeoutError, OSError, ValueError):
        out.update(status="network_error", kind="network_error")
    return out


def main():
    urls = [s.strip() for s in CATALOG.read_text(encoding="utf-8").splitlines() if s.strip()]
    if len(set(urls)) != len(urls):
        raise RuntimeError("Duplicate URLs in registry")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(inspect, urls))
    kind_counts = dict(Counter(x["kind"] for x in results))
    good = [x for x in results if x["status"] == "ok" and x["vless"] > 0
            and x["kind"] in {"vless_text", "vless_base64", "singbox_json"}]
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(results), "valid_content_sources": len(good),
        "kinds": kind_counts, "sources": results,
        "note": "URL contents are not proof of live VLESS tunnel; cloud probes remain mandatory."
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = [f"GWZHUB SOURCES {report['checked_at_utc']}",
            f"Total {len(results)}, valid VLESS-containing files {len(good)}", ""]
    rows.extend(f"{x['status']:16} {x['kind']:31} {x['vless']:6}  {x['url']}" for x in results)
    TEXT_OUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(results), "valid_content_sources": len(good),
                      "kinds": kind_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
