"""
Config Hub
Statistics generator
"""

import json
import os
from datetime import datetime


INPUT = "data/validated.txt"

OUTPUT = "data/stats.json"



def count_records():

    if not os.path.exists(INPUT):
        return 0

    with open(
        INPUT,
        "r",
        encoding="utf-8"
    ) as f:

        return len(
            [
                x
                for x in f.readlines()
                if x.strip()
            ]
        )



def generate():

    data = {

        "updated":
            datetime.utcnow().isoformat(),

        "valid_records":
            count_records(),

        "status":
            "ok"
    }


    os.makedirs(
        "data",
        exist_ok=True
    )


    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(data)



if __name__ == "__main__":

    generate()
