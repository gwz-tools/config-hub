"""Source availability/status manager."""
import json
import os
from datetime import datetime, timezone

STATUS_FILE = "data/source_status.json"
os.makedirs("data", exist_ok=True)

def load_status():
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # tolerate the short-lived {"sources": [...]} schema if encountered
    if isinstance(data, dict) and isinstance(data.get("sources"), list):
        return {x.get("name", f"source-{i}"): x for i, x in enumerate(data["sources"])}
    return data if isinstance(data, dict) else {}

def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_source(name, success, records=None):
    data = load_status()
    item = data.get(name, {
        "status": "unknown",
        "fail_count": 0,
        "last_success": None,
        "last_check": None,
        "records": 0,
        "history": [],
    })
    now = datetime.now(timezone.utc).isoformat()
    item["last_check"] = now
    item.setdefault("history", [])
    item.setdefault("records", 0)

    if success:
        item["status"] = "ok"
        item["fail_count"] = 0
        item["last_success"] = now
        if records is not None:
            item["records"] = int(records)
    else:
        item["fail_count"] = int(item.get("fail_count", 0)) + 1
        if item["fail_count"] >= 3:
            item["status"] = "failed"

    item["history"].append({"time": now, "ok": bool(success), "records": records})
    item["history"] = item["history"][-12:]
    data[name] = item
    save_status(data)

if __name__ == "__main__":
    print(json.dumps(load_status(), indent=2, ensure_ascii=False))
