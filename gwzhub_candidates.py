"""Build a compact candidate feed for GWZHUB.

Priority order follows sources.py. The feed is intentionally small: GitHub
collects broadly, while GWZHUB performs the authoritative real tunnel tests.
"""

from pathlib import Path
from urllib.parse import unquote
import re

from sources import get_sources
from collector import download, extract_vless, normalize_link, connection_identity

OUTPUT_FILE = Path("data/gwzhub_candidates.txt")
META_FILE = Path("data/gwzhub_candidates.meta")
LIMIT = 250
PER_SOURCE_LIMIT = 100


def build_candidates():
    selected = []
    seen = set()
    stats = []

    for source in get_sources():
        if len(selected) >= LIMIT:
            break

        name = source["name"]
        added = 0

        try:
            raw = download(source["url"])
            links = extract_vless(raw)

            for item in links:
                if added >= PER_SOURCE_LIMIT or len(selected) >= LIMIT:
                    break

                normalized = normalize_link(item, source)
                if not normalized:
                    continue

                identity = connection_identity(normalized)
                if identity in seen:
                    continue

                seen.add(identity)
                selected.append(normalized)
                added += 1

            stats.append(f"{name}={added}")
            print(f"GWZHUB candidates: {name} added={added}")

        except Exception as exc:
            stats.append(f"{name}=ERROR")
            print(f"GWZHUB candidates: {name} ERROR {exc}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        "\n".join(selected) + ("\n" if selected else ""),
        encoding="utf-8",
    )
    META_FILE.write_text(
        f"total={len(selected)}\n" + "\n".join(stats) + "\n",
        encoding="utf-8",
    )
    print(f"GWZHUB candidate feed written: {len(selected)}")


if __name__ == "__main__":
    build_candidates()
