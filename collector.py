"""
Config Hub
Collector

Downloads configuration data from registered sources.
"""

import os
import hashlib
import urllib.request
from datetime import datetime

from sources import get_sources


# ============================================================
# SETTINGS
# ============================================================

RAW_FILE = "data/raw.txt"
LOG_FILE = "logs/collector.log"


os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

def log(message):

    timestamp = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    line = f"{timestamp} {message}"

    print(line)

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:
        f.write(line + "\n")



# ============================================================
# DOWNLOAD
# ============================================================

def download(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Config-Hub-Collector/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=15
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="ignore"
        )



# ============================================================
# NORMALIZE
# ============================================================

def normalize(text):

    result = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        result.append(line)


    return "\n".join(result)



# ============================================================
# HASH
# ============================================================

def checksum(text):

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()



# ============================================================
# MAIN
# ============================================================

def main():

    sources = get_sources()

    log(
        f"Sources count: {len(sources)}"
    )


    collected = []

    success = 0


    for source in sources:

        name = source["name"]
        url = source["url"]

        try:

            log(
                f"Downloading {name}"
            )


            data = download(url)

            data = normalize(data)


            if data:

                collected.append(
                    f"# SOURCE: {name}\n{data}"
                )

                success += 1


                log(
                    f"OK {name} "
                    f"chars={len(data)} "
                    f"sha256={checksum(data)[:12]}"
                )


            else:

                log(
                    f"SKIP {name}: empty data"
                )


        except Exception as e:

            log(
                f"ERROR {name}: {e}"
            )



    output = "\n\n".join(
        collected
    )


    with open(
        RAW_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(output)



    log(
        f"Collection finished "
        f"sources={len(sources)} "
        f"success={success} "
        f"chars={len(output)}"
    )



if __name__ == "__main__":

    main()
