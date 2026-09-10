"""
GWZ Publisher

Publishes stable TOP pool
as public fast list.

Output:
- data/fast.txt
- fast.txt (GitHub Pages)
"""


import os
import shutil
from datetime import datetime


TOP_POOL = "data/top_pool.txt"

DATA_FAST = "data/fast.txt"

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



def copy_file(source, destination):

    if os.path.exists(source):

        shutil.copy(
            source,
            destination
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
            "TOP pool too small."
        )

        print(
            "Keep existing fast files."
        )

        return



    # backup existing data fast

    if os.path.exists(
        DATA_FAST
    ):

        shutil.copy(
            DATA_FAST,
            BACKUP
        )



    # update internal file

    copy_file(
        TOP_POOL,
        DATA_FAST
    )



    # update public GitHub Pages file

    copy_file(
        TOP_POOL,
        PUBLIC_FAST
    )


    print(
        "Published successfully"
    )


    print(
        "Configs:",
        count
    )


    print(
        "Time:",
        datetime.utcnow().isoformat()
    )



if __name__ == "__main__":

    publish()
