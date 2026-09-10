"""
Config Hub
History manager

Keeps previous validated datasets and protects
against unexpected source failures.
"""

import os
import json
from datetime import datetime


HISTORY_DIR = "history"

CURRENT_FILE = "data/validated.txt"

LAST_GOOD = os.path.join(
    HISTORY_DIR,
    "last_good.txt"
)

PREVIOUS = os.path.join(
    HISTORY_DIR,
    "previous_validated.txt"
)

STATUS_FILE = os.path.join(
    HISTORY_DIR,
    "source_status.json"
)


DROP_LIMIT = 0.5


def ensure_history():

    os.makedirs(
        HISTORY_DIR,
        exist_ok=True
    )


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


def save_lines(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        for item in data:
            f.write(
                item + "\n"
            )


def update_history():

    ensure_history()


    current = read_lines(
        CURRENT_FILE
    )


    previous = read_lines(
        LAST_GOOD
    )


    status = {
        "time":
            datetime.utcnow().isoformat(),

        "current_count":
            len(current),

        "previous_count":
            len(previous),

        "decision":
            ""
    }


    # Первый запуск

    if not previous:

        save_lines(
            LAST_GOOD,
            current
        )

        save_lines(
            PREVIOUS,
            current
        )


        status["decision"] = (
            "initial_dataset_saved"
        )


    else:

        if len(current) < len(previous) * DROP_LIMIT:


            # слишком большое падение

            save_lines(
                PREVIOUS,
                previous
            )


            status["decision"] = (
                "large_drop_detected_keep_previous"
            )


        else:


            save_lines(
                PREVIOUS,
                previous
            )


            save_lines(
                LAST_GOOD,
                current
            )


            status["decision"] = (
                "dataset_updated"
            )


    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            status,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        json.dumps(
            status,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":

    update_history()
