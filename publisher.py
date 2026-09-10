"""
GWZ Publisher

Publishes stable TOP pool
as public fast list.
"""

import os
import shutil
from datetime import datetime


TOP_POOL = "data/top_pool.txt"

FAST_FILE = "fast.txt"

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

    shutil.copy(
        src,
        dst
    )



def publish():

    top_count = count_lines(
        TOP_POOL
    )


    print(
        "TOP pool size:",
        top_count
    )


    #
    # Есть хороший TOP pool
    #
    if top_count >= MIN_CONFIGS:

        if os.path.exists(
            FAST_FILE
        ):

            copy_file(
                FAST_FILE,
                BACKUP
            )


        copy_file(
            TOP_POOL,
            FAST_FILE
        )


        print(
            "fast.txt updated"
        )


    #
    # TOP маленький
    #
    else:

        print(
            "TOP pool too small"
        )


        #
        # Старый fast.txt сохраняем
        #
        if os.path.exists(
            FAST_FILE
        ):

            print(
                "Keeping existing fast.txt"
            )


        #
        # Если файла нет вообще
        # создаём безопасный
        #
        else:

            with open(
                FAST_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    "# GWZ fast pool\n"
                )


            print(
                "Created initial fast.txt"
            )


    print(
        "Publisher finished:",
        datetime.utcnow()
    )



if __name__ == "__main__":

    publish()
