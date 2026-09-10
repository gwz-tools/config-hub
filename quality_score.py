import json
from pathlib import Path
from datetime import datetime, timezone


STATUS_FILE = Path("data/source_status.json")
OUTPUT_FILE = Path("data/source_quality.json")


def calculate_score(item):

    score = 0

    status = item.get("status")

    records = item.get("records", 0)

    history = item.get("history", [])


    # загрузка прошла
    if status == "ok":
        score += 40


    # есть данные
    if records > 0:
        score += 30


    # стабильность
    if len(history) >= 3:
        score += 20


    # небольшой бонус
    if records >= 50:
        score += 10


    if score >= 80:
        grade = "GOOD"

    elif score >= 50:
        grade = "WARNING"

    else:
        grade = "DEAD"


    return score, grade



def main():

    if not STATUS_FILE.exists():
        print("source_status.json not found")
        return


    with open(
        STATUS_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)


    result = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),
        "sources": []
    }


    for item in data.get("sources", []):

        score, grade = calculate_score(item)

        item["quality_score"] = score
        item["grade"] = grade

        result["sources"].append(item)


    OUTPUT_FILE.parent.mkdir(
        exist_ok=True
    )


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        "Quality score generated:",
        len(result["sources"])
    )



if __name__ == "__main__":
    main()
