"""
Config Hub

Last good snapshot manager.

Keeps the last validated working data.
"""

import os
import shutil
from datetime import datetime


SOURCE_FILE = "data/validated.txt"

GOOD_FILE = "data/last_good.txt"

META_FILE = "data/last_good.json"



def save_last_good():

    if not os.path.exists(SOURCE_FILE):

        print(
            "No validated data found"
        )

        return



    shutil.copy2(
        SOURCE_FILE,
        GOOD_FILE
    )



    meta = {
        "updated": datetime.utcnow().isoformat(),
        "source": SOURCE_FILE
    }



    import json


    with open(
        META_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            meta,
            f,
            indent=2,
            ensure_ascii=False
        )



    print(
        "Last good snapshot updated"
    )



def restore_last_good():

    if not os.path.exists(GOOD_FILE):

        print(
            "No last good snapshot"
        )

        return False



    shutil.copy2(
        GOOD_FILE,
        SOURCE_FILE
    )


    print(
        "Restored last good snapshot"
    )


    return True



if __name__ == "__main__":

    save_last_good()
