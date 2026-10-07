"""Build a compact, geographically balanced VLESS candidate feed for GWZHUB.

GitHub only performs discovery/preselection. GWZHUB remains authoritative for
real tunnel/liveness checks from the target network.
"""

from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import unquote
import re

from sources import get_sources
from collector import download, extract_vless, normalize_link, connection_identity

OUTPUT_FILE = Path("data/gwzhub_candidates.txt")
META_FILE = Path("data/gwzhub_candidates.meta")
LIMIT = 250
MIN_SAFE_POOL = 80

# Preferred for the target geography. This is ordering, not a hard exclusion.
COUNTRY_ORDER = ["NL", "LT", "DE", "FI", "LV", "PL", "EE", "SE", "US", "CA", "GB", "OTHER"]

COUNTRY_NAMES = {
    "NL": "Netherlands", "LT": "Lithuania", "DE": "Germany",
    "FI": "Finland", "LV": "Latvia", "PL": "Poland",
    "EE": "Estonia", "SE": "Sweden", "US": "United States",
    "CA": "Canada", "GB": "United Kingdom",
}
NAME_TO_CODE = {v.lower(): k for k, v in COUNTRY_NAMES.items()}


def country_from_link(link):
    remark = unquote(link.split("#", 1)[1] if "#" in link else "").strip()

    # Normalized collector remark: FLAG | GWZ | Country ...
    m = re.search(r"\|\s*GWZ\s*\|\s*([^|\[]+)", remark, re.I)
    text = (m.group(1) if m else remark).strip()

    # Exact/leading country name.
    low = text.lower()
    for name, code in sorted(NAME_TO_CODE.items(), key=lambda x: len(x[0]), reverse=True):
        if low == name or low.startswith(name + " "):
            return code

    # Handles upstream remarks that became "Unknown US", "Unknown NL", etc.
    m = re.search(r"(?:^|\s)(NL|LT|DE|FI|LV|PL|EE|SE|US|CA|GB)(?:$|\s)", text, re.I)
    if m:
        return m.group(1).upper()

    # Flag emoji.
    m = re.search(r"([\U0001F1E6-\U0001F1FF])([\U0001F1E6-\U0001F1FF])", remark)
    if m:
        return "".join(chr(ord(ch) - 127397) for ch in m.group(0))

    return "OTHER"


def round_robin_source(buckets, limit):
    """Avoid letting one upstream monopolize a country bucket."""
    queues = {name: deque(items) for name, items in buckets.items() if items}
    out = []
    while queues and len(out) < limit:
        for name in list(queues):
            q = queues[name]
            if q:
                out.append(q.popleft())
                if len(out) >= limit:
                    break
            if not q:
                queues.pop(name, None)
    return out


def build_candidates():
    # country -> source -> configs
    pools = defaultdict(lambda: defaultdict(list))
    seen = set()
    source_stats = {}
    country_seen = defaultdict(int)

    # Scan the FULL source. The old code took the first 100 from each source,
    # which systematically hid NL/LT appearing later in upstream lists.
    for source in get_sources():
        name = source["name"]
        accepted = 0
        try:
            raw = download(source["url"])
            for item in extract_vless(raw):
                normalized = normalize_link(item, source)
                if not normalized:
                    continue
                identity = connection_identity(normalized)
                if identity in seen:
                    continue
                seen.add(identity)
                cc = country_from_link(normalized)
                pools[cc][name].append(normalized)
                country_seen[cc] += 1
                accepted += 1
            source_stats[name] = accepted
            print(f"GWZHUB scan: {name} unique={accepted}")
        except Exception as exc:
            source_stats[name] = "ERROR"
            print(f"GWZHUB scan: {name} ERROR {exc}")

    selected = []
    selected_ids = set()
    selected_country = defaultdict(int)

    def add(items, cap):
        for cfg in items:
            if len(selected) >= LIMIT or cap <= 0:
                break
            ident = connection_identity(cfg)
            if ident in selected_ids:
                continue
            selected.append(cfg)
            selected_ids.add(ident)
            selected_country[country_from_link(cfg)] += 1
            cap -= 1

    # Guarantee useful representation of nearby preferred countries when present.
    # Caps are intentionally generous enough for GWZHUB to discover alternatives.
    preferred_caps = {
        "NL": 30, "LT": 20, "DE": 30, "FI": 25,
        "LV": 20, "PL": 25, "EE": 15, "SE": 15,
        "US": 25, "CA": 15, "GB": 10,
    }

    for cc in COUNTRY_ORDER:
        if cc == "OTHER":
            continue
        items = round_robin_source(pools.get(cc, {}), preferred_caps.get(cc, 10))
        add(items, preferred_caps.get(cc, 10))

    # Fill remaining capacity from every country/source, still round-robin.
    remainder = defaultdict(list)
    for cc, by_source in pools.items():
        for name, items in by_source.items():
            for cfg in items:
                if connection_identity(cfg) not in selected_ids:
                    remainder[name].append(cfg)
    add(round_robin_source(remainder, LIMIT - len(selected)), LIMIT - len(selected))

    # Safety: a transient upstream collapse must not replace a healthy previous feed.
    if len(selected) < MIN_SAFE_POOL and OUTPUT_FILE.exists():
        old = [x for x in OUTPUT_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
        if len(old) >= MIN_SAFE_POOL:
            print(f"GWZHUB candidate guard: new={len(selected)} old={len(old)}; keeping old")
            return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(selected) + ("\n" if selected else ""), encoding="utf-8")

    meta = [
        f"total={len(selected)}",
        "policy=geo-balanced-full-source-scan",
        "preferred=" + ",".join(COUNTRY_ORDER[:-1]),
    ]
    meta += [f"source.{k}={v}" for k, v in source_stats.items()]
    meta += [f"available.{k}={country_seen[k]}" for k in sorted(country_seen)]
    meta += [f"selected.{k}={selected_country[k]}" for k in sorted(selected_country)]
    META_FILE.write_text("\n".join(meta) + "\n", encoding="utf-8")

    print(f"GWZHUB candidate feed written: {len(selected)}")
    print("Selected countries:", dict(sorted(selected_country.items())))


if __name__ == "__main__":
    build_candidates()
