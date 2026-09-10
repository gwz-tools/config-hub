"""
Config Hub
Statistics module

Creates technical statistics for collected data.
"""

import os
import json
from datetime import datetime


DATA_DIR = "data"

RAW_FILE = os.path.join(DATA_DIR, "raw.txt")
VALID_FILE = os.path.join(DATA_DIR, "validated.txt")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")


def count_lines(path):
    if not os.path.exists(path):
        return 0

    with open(path, "r", encoding="utf-8") as f:
        return len(
            [
                x.strip()
                for x in f.readlines()
                if x.strip()
            ]
        )


def main():

    os.makedirs(DATA_DIR, exist_ok=True)

    stats = {
        "updated": datetime.utcnow().isoformat(),
        "raw_records": count_lines(RAW_FILE),
        "valid_records": count_lines(VALID_FILE),
        "status": "ok"
    }


    with open(
        STATS_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            stats,
            f,
            indent=2
        )


    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
