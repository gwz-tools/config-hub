#!/bin/sh
# Install an ISOLATED Mamin candidate source on GWZHUB (NOT on OpenWrt).
# Does not modify GWZHUB's public publisher, Podkop or system services.
set -eu

PROJECT="https://raw.githubusercontent.com/gwz-tools/config-hub/main"
INSTALL_DIR="/opt/gwzhub/mamin-source"
STATE_DIR="/opt/gwzhub/data/mamin"
APK_PATH="$STATE_DIR/Mamin-VPN-0.9.29.apk"
EXPECTED_APK_SHA256="70df40e973a4e0af4dbd2465bb398455794117da7be6c075b3afe78d698313fb"

if [ -f /etc/openwrt_release ]; then
  echo "Refusing to install on OpenWrt: use the GWZHUB Linux host, not the Dunay router." >&2
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo/root on GWZHUB (not on the Dunay router)." >&2
  exit 1
fi

for tool in python3 curl openssl sha256sum sing-box; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required tool missing: $tool. Nothing was installed." >&2
    exit 1
  fi
done

umask 077
mkdir -p "$INSTALL_DIR" "$STATE_DIR"
FREE_KB="$(df -Pk "$STATE_DIR" | awk 'NR==2 {print $4}')"
if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt 102400 ]; then
  echo "Need at least 100 MiB free on GWZHUB before downloading APK." >&2
  exit 1
fi
chmod 700 "$INSTALL_DIR" "$STATE_DIR"

# Download source scripts into a private staging directory, then install.
TEMP="$(mktemp -d "$INSTALL_DIR/.setup-XXXXXX")"
trap 'rm -rf "$TEMP"' EXIT HUP INT TERM
for name in mamin_hub_update.py mamin_verify_import.py mamin_signing_key.py cloud_verified.py; do
  curl --fail --silent --show-error --location --retry 2 \
    "$PROJECT/$name" -o "$TEMP/$name"
done
python3 -m py_compile "$TEMP/mamin_hub_update.py" "$TEMP/mamin_verify_import.py" \
  "$TEMP/mamin_signing_key.py" "$TEMP/cloud_verified.py"
for name in mamin_hub_update.py mamin_verify_import.py mamin_signing_key.py cloud_verified.py; do
  install -m 0600 "$TEMP/$name" "$INSTALL_DIR/$name"
done

if [ ! -s "$APK_PATH" ] ||
   ! echo "$EXPECTED_APK_SHA256  $APK_PATH" | sha256sum -c - >/dev/null 2>&1; then
  echo "Downloading exact audited APK to the private GWZHUB data directory ..."
  curl --fail --silent --show-error --location --retry 2 \
    --connect-timeout 15 --max-time 240 \
    "https://www.tvbox.one/atv-release/Mamin-VPN-0.9.29.apk" \
    -o "$TEMP/Mamin-VPN-0.9.29.apk"
  echo "$EXPECTED_APK_SHA256  $TEMP/Mamin-VPN-0.9.29.apk" | sha256sum -c -
  install -m 0600 "$TEMP/Mamin-VPN-0.9.29.apk" "$APK_PATH"
fi
echo "$EXPECTED_APK_SHA256  $APK_PATH" | sha256sum -c -

echo "Mamin source staged securely; no publisher, router or cron changed."
echo "Run once to validate live endpoints:"
echo "python3 $INSTALL_DIR/mamin_hub_update.py --apk-file $APK_PATH --data-dir $STATE_DIR"
echo "Inspect safe status:"
echo "cat $STATE_DIR/status.json"
echo "Private last-good feed (only after >=3 verified tunnels):"
echo "$STATE_DIR/mamin-private-live.txt"
