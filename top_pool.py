"""
GWZ TOP Pool selector

Selects most stable configurations
using quality history.
"""

import os
import json


VALIDATED_FILE = "data/validated.txt"

QUALITY_FILE = (
    "history/quality/sources.json"
)

OUTPUT_FILE = (
    "data/top_pool.txt"
)


MIN_SCORE = 70

TOP_LIMIT = 50



def read_lines(path):

    if not os.path.exists(path):
        return []

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return [
            x.strip()
            for x in f.readlines()
            if x.strip()
        ]



def load_quality():

    if not os.path.exists(
        QUALITY_FILE
    ):
        return {}

    with open(
        QUALITY_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



def build_pool():

    configs = read_lines(
        VALIDATED_FILE
    )


    quality = load_quality()


    ranked = []


    for cfg in configs:

        info = quality.get(
            cfg,
            {}
        )


        score = info.get(
            "score",
            0
        )


        fails = info.get(
            "fails",
            99
        )


        success = info.get(
            "success",
            0
        )


        if score >= MIN_SCORE and fails < 3:


            ranked.append(
                (
                    score,
                    success,
                    cfg
                )
            )



    ranked.sort(
        reverse=True
    )


    result = [
        x[2]
        for x in ranked[:TOP_LIMIT]
    ]


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for item in result:

            f.write(
                item + "\n"
            )


    print(
        "TOP pool:",
        len(result)
    )



if __name__ == "__main__":

    build_pool()
