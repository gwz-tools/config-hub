"""
Config Hub
Fallback manager

Restores last known good snapshot
when validation fails.
"""

import os
import shutil
from datetime import datetime


DATA_DIR = "data"

VALID_FILE = "data/validated.txt"
BACKUP_FILE = "data/last_good.txt"

LOG_FILE = "logs/fallback.log"



def log(message):

    os.makedirs("logs", exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.utcnow()} {message}\n"
        )



def check_valid():

    if not os.path.exists(VALID_FILE):
        return False

    size = os.path.getsize(VALID_FILE)

    return size > 100



def restore():

    if not os.path.exists(BACKUP_FILE):

        log(
            "No last_good snapshot available"
        )

        return False


    shutil.copy(
        BACKUP_FILE,
        VALID_FILE
    )


    log(
        "Restored last_good snapshot"
    )

    return True



def main():

    if check_valid():

        log(
            "Validation OK, no fallback needed"
        )

        return


    log(
        "Validation failed, starting fallback"
    )


    restore()



if __name__ == "__main__":
    main()
