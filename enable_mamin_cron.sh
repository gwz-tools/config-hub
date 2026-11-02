#!/bin/sh
# Opt-in schedule for PRIVATE GWZHUB Mamin updater, only after healthy smoke test.
set -eu
if [ -e /etc/openwrt_release ]; then
  echo "Do not schedule on OpenWrt/Dunay." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Run as GWZHUB root (sudo)." >&2
  exit 1
fi
if ! command -v crontab >/dev/null 2>&1; then
  echo "crontab not found; install cron on GWZHUB before scheduling." >&2
  exit 1
fi
python3 - <<'PY'
import json
from pathlib import Path
root = Path("/opt/gwzhub/data/mamin")
s = json.loads((root/"status.json").read_text())
if (s.get("status") != "healthy" or not s.get("signature_verified")
        or not s.get("feed_updated") or int(s.get("end_to_end_passed", 0)) < 3
        or not (root/"mamin-private-live.txt").is_file()):
    raise SystemExit("First live Mamin source update must pass before cron is enabled.")
print("Last healthy Mamin smoke test:", s["end_to_end_passed"], "verified tunnels")
PY
PYTHON="$(command -v python3)"
EXISTING="$(crontab -l 2>/dev/null || true)"
if printf '%s\n' "$EXISTING" | grep -Fq 'mamin_hub_update.py'; then
  echo "Mamin cron already installed; not adding a duplicate."
  exit 0
fi
NEW="39 3,9,15,21 * * * $PYTHON /opt/gwzhub/mamin-source/mamin_hub_update.py --apk-file /opt/gwzhub/data/mamin/Mamin-VPN-0.9.29.apk --data-dir /opt/gwzhub/data/mamin >/dev/null 2>&1 # gwzhub-mamin-private"
{
  [ -z "$EXISTING" ] || printf '%s\n' "$EXISTING"
  printf '%s\n' "$NEW"
} | crontab -
echo "Scheduled private Mamin verification every six hours (GWZHUB local clock)."
echo "No public feeds, GWZHUB DB or Dunay router modified."
