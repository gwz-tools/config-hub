"""
Config Hub
Source collector

Downloads public data from configured sources.
This module only collects public information.
"""


import os
import time
import hashlib
import requests
from datetime import datetime

from sources import get_sources


CACHE_DIR = "cache"
DATA_DIR = "data"
LOG_DIR = "logs"


TIMEOUT = 15


for folder in [
    CACHE_DIR,
    DATA_DIR,
    LOG_DIR
]:
    os.makedirs(folder, exist_ok=True)



def log(message):

    text = (
        datetime.utcnow()
        .strftime("%Y-%m-%d %H:%M:%S")
        +
        " "
        +
        message
        +
        "\n"
    )

    print(text.strip())

    with open(
        os.path.join(
            LOG_DIR,
            "collector.log"
        ),
        "a",
        encoding="utf-8"
    ) as f:

        f.write(text)



def hash_data(data):

    return hashlib.sha256(
        data.encode(
            "utf-8",
            errors="ignore"
        )
    ).hexdigest()



def download_source(source):

    name = source["name"]

    url = source["url"]


    if not url:

        log(
            f"SKIP {name}: empty url"
        )

        return ""


    try:

        log(
            f"Downloading {name}"
        )


        headers = {

            "User-Agent":
            "ConfigHubCollector/1.0"

        }


        r = requests.get(
            url,
            timeout=TIMEOUT,
            headers=headers
        )


        r.raise_for_status()


        return r.text


    except Exception as e:


        log(
            f"ERROR {name}: {e}"
        )


        return ""



def save_result(content):

    filename = os.path.join(
        DATA_DIR,
        "raw.txt"
    )


    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)



def run():


    all_data = []

    sources = get_sources()


    log(
        f"Sources count: {len(sources)}"
    )


    for source in sources:


        data = download_source(
            source
        )


        if data:


            all_data.append(
                data
            )


        # небольшая пауза
        time.sleep(3)



    result = "\n".join(
        all_data
    )


    save_result(
        result
    )


    log(
        "Collection finished"
    )


    log(
        f"Collected chars: {len(result)}"
    )



if __name__ == "__main__":

    run()
