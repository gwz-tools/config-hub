"""
Config Hub
Validator

Checks collected public configuration data.
Removes duplicates and invalid entries.
"""


import os
import hashlib
from datetime import datetime


RAW_FILE = "data/raw.txt"
OUTPUT_FILE = "data/validated.txt"


os.makedirs(
    "data",
    exist_ok=True
)



def log(message):

    print(
        datetime.utcnow()
        .strftime("%Y-%m-%d %H:%M:%S"),
        message
    )



def normalize(line):

    return (
        line
        .strip()
        .replace(
            "\r",
            ""
        )
    )



def fingerprint(value):

    return hashlib.md5(
        value.encode(
            "utf-8",
            errors="ignore"
        )
    ).hexdigest()



def validate():

    if not os.path.exists(
        RAW_FILE
    ):

        log(
            "No raw data"
        )

        return


    with open(
        RAW_FILE,
        encoding="utf-8",
        errors="ignore"
    ) as f:

        lines = f.readlines()



    result = []

    seen = set()


    for line in lines:


        item = normalize(
            line
        )


        if not item:

            continue



        key = fingerprint(
            item
        )


        if key in seen:

            continue



        seen.add(
            key
        )


        result.append(
            item
        )



    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for item in result:

            f.write(
                item + "\n"
            )


    log(
        f"Input: {len(lines)}"
    )

    log(
        f"Output: {len(result)}"
    )



if __name__ == "__main__":

    validate()
