"""
GWZ Config Hub

Collector v1.6.7

Downloads sources,
extracts VLESS configs,
removes duplicates,
creates raw pool.
"""


import os
import re
import hashlib
import urllib.request


from datetime import datetime


from sources import get_sources
from source_status import update_source



# ============================================================
# PATHS
# ============================================================


RAW_FILE = "data/raw.txt"

LOG_FILE = "logs/collector.log"



os.makedirs(
    "data",
    exist_ok=True
)


os.makedirs(
    "logs",
    exist_ok=True
)



# ============================================================
# LOG
# ============================================================


def log(message):

    timestamp = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    line = (
        f"{timestamp} {message}"
    )


    print(line)


    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            line + "\n"
        )



# ============================================================
# DOWNLOAD
# ============================================================


def download(url):

    request = urllib.request.Request(

        url,

        headers={
            "User-Agent":
            "GWZ-Collector/1.6.7"
        }

    )


    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:


        return response.read().decode(

            "utf-8",

            errors="ignore"

        )



# ============================================================
# EXTRACT VLESS
# ============================================================


def extract_vless(text):


    pattern = r"vless://[^\s<>\"']+"


    return re.findall(

        pattern,

        text,

        flags=re.MULTILINE

    )



# ============================================================
# NORMALIZE
# ============================================================


def normalize_link(link):

    return (

        link

        .strip()

        .replace(
            "\r",
            ""
        )

    )



# ============================================================
# DEDUPLICATION
# ============================================================


def remove_duplicates(items):


    result = []

    seen = set()


    for item in items:


        key = hashlib.sha256(

            item.encode(
                "utf-8"
            )

        ).hexdigest()



        if key not in seen:


            seen.add(key)

            result.append(item)



    return result



# ============================================================
# HASH
# ============================================================


def checksum(text):

    return hashlib.sha256(

        text.encode(
            "utf-8"
        )

    ).hexdigest()



# ============================================================
# MAIN
# ============================================================


def main():


    sources = get_sources()


    log(
        f"Sources count: {len(sources)}"
    )



    all_links = []



    success = 0

    failed = 0



    for source in sources:


        name = source["name"]

        url = source["url"]



        try:


            log(
                f"Downloading {name}"
            )



            data = download(url)



            log(
                f"Downloaded {name} chars={len(data)}"
            )



            links = extract_vless(
                data
            )



            links = [

                normalize_link(x)

                for x in links

            ]



            if links:


                all_links.extend(
                    links
                )


                success += 1



                update_source(
                    name,
                    True
                )



                log(

                    f"OK {name} "
                    f"links={len(links)}"

                )



            else:


                failed += 1


                update_source(
                    name,
                    False
                )


                log(
                    f"EMPTY {name}"
                )



        except Exception as e:


            failed += 1


            update_source(
                name,
                False
            )


            log(
                f"ERROR {name}: {e}"
            )



    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================


    before = len(all_links)


    all_links = remove_duplicates(
        all_links
    )


    after = len(all_links)



    # ========================================================
    # SAVE
    # ========================================================


    output = "\n".join(
        all_links
    )



    with open(

        RAW_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write(
            output
        )



    log(

        "Collection finished "

        f"sources={len(sources)} "

        f"success={success} "

        f"failed={failed} "

        f"before={before} "

        f"after={after} "

        f"sha256={checksum(output)[:12]}"

    )




if __name__ == "__main__":

    main()
