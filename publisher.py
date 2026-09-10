"""
GWZ Publisher

Publishes stable TOP pool
as public fast list.
"""

import os
import shutil
from datetime import datetime


TOP_POOL = "data/top_pool.txt"

FAST_FILE = "data/fast.txt"

BACKUP = "data/fast_backup.txt"


MIN_CONFIGS = 5



def count_lines(path):

    if not os.path.exists(path):
        return 0

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return len(
            [
                x for x in f.readlines()
                if x.strip()
            ]
        )



def publish():

    count = count_lines(
        TOP_POOL
    )


    print(
        "TOP pool size:",
        count
    )


    if count < MIN_CONFIGS:

        print(
            "TOP pool too small. Keep old fast.txt"
        )

        return


    if os.path.exists(
        FAST_FILE
    ):

        shutil.copy(
            FAST_FILE,
            BACKUP
        )


    shutil.copy(
        TOP_POOL,
        FAST_FILE
    )


    print(
        "fast.txt updated",
        datetime.utcnow()
    )



if __name__ == "__main__":

    publish()
