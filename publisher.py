"""
GWZ Publisher

Publishes stable TOP pool
as public fast list.

Creates:
- data/fast.txt
- fast.txt (GitHub Pages public file)

Protects old version with backup.
"""

import os
import shutil
from datetime import datetime


TOP_POOL = "data/top_pool.txt"

FAST_FILE = "data/fast.txt"

PUBLIC_FAST = "fast.txt"

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



def copy_file(src, dst):

    folder = os.path.dirname(dst)

    if folder:
        os.makedirs(
            folder,
            exist_ok=True
        )

    shutil.copy(
        src,
        dst
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


    #
    # backup previous public list
    #

    if os.path.exists(
        FAST_FILE
    ):

        copy_file(
            FAST_FILE,
            BACKUP
        )


    #
    # create internal fast file
    #

    copy_file(
        TOP_POOL,
        FAST_FILE
    )


    #
    # create GitHub Pages public file
    #

    copy_file(
        TOP_POOL,
        PUBLIC_FAST
    )


    print(
        "fast.txt updated"
    )

    print(
        "Published:",
        datetime.utcnow().isoformat()
    )



if __name__ == "__main__":

    publish()
