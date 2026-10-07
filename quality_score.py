"""Generate source-level quality information from source_status.json."""
import json
from pathlib import Path
from datetime import datetime, timezone

STATUS_FILE = Path("data/source_status.json")
OUTPUT_FILE = Path("data/source_quality.json")

def calculate_score(item):
    score = 0
    if item.get("status") == "ok":
        score += 50
    if int(item.get("records", 0) or 0) > 0:
        score += 20
    history = item.get("history", []) or []
    recent = history[-6:]
    if recent:
        ratio = sum(1 for x in recent if x.get("ok")) / len(recent)
        score += round(30 * ratio)
    elif item.get("last_success"):
        score += 20
    score = min(100, score)
    grade = "GOOD" if score >= 70 else ("WARNING" if score >= 40 else "DEAD")
    return score, grade

def main():
    if not STATUS_FILE.exists():
        raise SystemExit("source_status.json not found")
    data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("sources"), list):
        items = [(x.get("name", "unknown"), x) for x in data["sources"]]
    elif isinstance(data, dict):
        items = list(data.items())
    else:
        items = []

    result = {"updated": datetime.now(timezone.utc).isoformat(), "sources": []}
    for name, item in items:
        row = dict(item)
        score, grade = calculate_score(row)
        row["name"] = name
        row["quality_score"] = score
        row["grade"] = grade
        result["sources"].append(row)

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Quality score generated:", len(result["sources"]))

if __name__ == "__main__":
    main()
