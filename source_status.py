"""
Config Hub
Source status manager

Tracks source availability history.
"""

import json
import os
from datetime import datetime


STATUS_FILE = "data/source_status.json"


os.makedirs(
    "data",
    exist_ok=True
)


def load_status():

    if not os.path.exists(STATUS_FILE):
        return {}

    with open(
        STATUS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



def save_status(data):

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )



def update_source(
    name,
    success
):

    data = load_status()


    item = data.get(
        name,
        {
            "status": "unknown",
            "fail_count": 0,
            "last_success": None
        }
    )


    if success:

        item["status"] = "ok"
        item["fail_count"] = 0
        item["last_success"] = (
            datetime.utcnow()
            .isoformat()
        )


    else:

        item["fail_count"] += 1

        if item["fail_count"] >= 3:

            item["status"] = "failed"



    data[name] = item


    save_status(data)



if __name__ == "__main__":

    print(
        json.dumps(
            load_status(),
            indent=2
        )
    )
