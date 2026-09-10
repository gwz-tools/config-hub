"""
Config Hub
History manager v2

Tracks dataset history and
individual source stability.
"""

import os
import json
from datetime import datetime


HISTORY_DIR = "history"

QUALITY_DIR = os.path.join(
    HISTORY_DIR,
    "quality"
)

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

    os.makedirs(
        QUALITY_DIR,
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


def load_quality_history():

    path = os.path.join(
        QUALITY_DIR,
        "sources.json"
    )

    if not os.path.exists(path):
        return {}

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_quality_history(data):

    path = os.path.join(
        QUALITY_DIR,
        "sources.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def update_quality(validated):

    history = load_quality_history()

    today = datetime.utcnow().strftime(
        "%Y-%m-%d"
    )


    for source in validated:


        if source not in history:

            history[source] = {

                "score": 100,

                "success": 1,

                "fails": 0,

                "first_seen": today,

                "last_seen": today
            }


        else:

            history[source]["success"] += 1

            history[source]["fails"] = 0

            history[source]["last_seen"] = today


    # отсутствующие источники

    for source in list(history.keys()):

        if source not in validated:

            history[source]["fails"] += 1

            history[source]["score"] -= 10


            if history[source]["score"] < 0:

                history[source]["score"] = 0


    save_quality_history(
        history
    )


    snapshot = os.path.join(
        QUALITY_DIR,
        today + ".json"
    )


    with open(
        snapshot,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            history,
            f,
            indent=2,
            ensure_ascii=False
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


    update_quality(
        current
    )


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
