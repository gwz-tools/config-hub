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

for tool in python3 curl openssl sha256sum tar; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required tool missing: $tool. Nothing was installed." >&2
    exit 1
  fi
done

umask 077
mkdir -p "$INSTALL_DIR" "$STATE_DIR"
FREE_KB="$(df -Pk "$STATE_DIR" | awk 'NR==2 {print $4}')"
if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt 204800 ]; then
  echo "Need at least 200 MiB free on GWZHUB for an isolated Sing-box and APK." >&2
  exit 1
fi
chmod 700 "$INSTALL_DIR" "$STATE_DIR"
if [ "$(uname -m)" != "x86_64" ]; then
  echo "Installer expects Debian amd64/x86_64 on GWZHUB." >&2
  exit 1
fi

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
curl --fail --silent --show-error --location --retry 2 \
  "$PROJECT/enable_mamin_cron.sh" -o "$TEMP/enable_mamin_cron.sh"
sh -n "$TEMP/enable_mamin_cron.sh"
install -m 0700 "$TEMP/enable_mamin_cron.sh" "$INSTALL_DIR/enable_mamin_cron.sh"

# Install a private, version-pinned sing-box; never change system services.
SB_VERSION="1.12.22"
SB_ASSET="sing-box-${SB_VERSION}-linux-amd64.tar.gz"
SB_PATH="$INSTALL_DIR/bin/sing-box"
if [ ! -x "$SB_PATH" ] || ! "$SB_PATH" version 2>/dev/null | grep -Fq "$SB_VERSION"; then
  echo "Preparing isolated sing-box $SB_VERSION for Mamin (not a system service) ..."
  curl --fail --silent --show-error --location --retry 2 \
    --connect-timeout 15 --max-time 45 \
    "https://api.github.com/repos/SagerNet/sing-box/releases/tags/v$SB_VERSION" \
    -o "$TEMP/sing-box-release.json"
  EXPECTED_SB_HASH="$(python3 - "$TEMP/sing-box-release.json" "$SB_ASSET" <<'PY'
import json, re, sys
from pathlib import Path
payload=json.loads(Path(sys.argv[1]).read_text())
asset=next((x for x in payload.get("assets",[]) if x.get("name")==sys.argv[2]), None)
if not asset or not isinstance(asset.get("digest"),str):
    raise SystemExit("No official SHA256 asset digest found; fail closed.")
digest=asset["digest"]
if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
    raise SystemExit("Unexpected GitHub asset digest; fail closed.")
print(digest.split(":",1)[1].lower())
PY
)"
  curl --fail --silent --show-error --location --retry 2 \
    --connect-timeout 15 --max-time 240 \
    "https://github.com/SagerNet/sing-box/releases/download/v$SB_VERSION/$SB_ASSET" \
    -o "$TEMP/$SB_ASSET"
  echo "$EXPECTED_SB_HASH  $TEMP/$SB_ASSET" | sha256sum -c -
  tar -xzf "$TEMP/$SB_ASSET" -C "$TEMP" \
    "sing-box-${SB_VERSION}-linux-amd64/sing-box"
  mkdir -p "$INSTALL_DIR/bin"
  chmod 700 "$INSTALL_DIR/bin"
  install -m 0700 "$TEMP/sing-box-${SB_VERSION}-linux-amd64/sing-box" "$SB_PATH"
fi
"$SB_PATH" version | head -n 1

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

echo "Mamin source staged securely; private sing-box: $SB_PATH"
echo "No publisher, router or cron changed."
echo "Run once to validate live endpoints:"
echo "python3 $INSTALL_DIR/mamin_hub_update.py --apk-file $APK_PATH --data-dir $STATE_DIR"
echo "Inspect safe status:"
echo "cat $STATE_DIR/status.json"
echo "Private last-good feed (only after >=3 verified tunnels):"
echo "$STATE_DIR/mamin-private-live.txt"

echo "After a healthy first run, optionally enable six-hour checks:"
echo "sh $INSTALL_DIR/enable_mamin_cron.sh"
