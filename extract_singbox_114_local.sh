#!/bin/sh
# Copy existing sing-box 1.14.2 from locally cached Docker image.
# No image pull and NO container process: docker create + export only.
set -eu
umask 077

IMAGE='gwzhub/sing-box:1.14.2'
OUT='/opt/gwzhub/mamin-source/bin/sing-box-1.14.2'

if [ "$(id -u)" -ne 0 ]; then
  echo 'Run with sudo on GWZHUB.' >&2
  exit 1
fi
if [ -e /etc/openwrt_release ]; then
  echo 'Refusing OpenWrt.' >&2
  exit 1
fi
for tool in docker tar mktemp install awk; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing: $tool" >&2; exit 1; }
done
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo 'Local sing-box image missing; no network pull attempted.' >&2
  exit 1
fi
if [ -x "$OUT" ] && "$OUT" version 2>/dev/null | grep -q '^sing-box version 1\.14\.2$'; then
  echo "Already installed: $OUT"
  exit 0
fi
mkdir -p /opt/gwzhub/mamin-source/bin
chmod 700 /opt/gwzhub/mamin-source/bin
TMPDIR_LOCAL="$(mktemp -d /opt/gwzhub/mamin-source/bin/.extract-114-XXXXXX)"
CID=''
cleanup() {
  if [ -n "$CID" ]; then docker rm -f "$CID" >/dev/null 2>&1 || true; fi
  rm -rf -- "$TMPDIR_LOCAL"
}
trap cleanup 0
trap 'exit 1' 1 2 3 15

# docker create/export only reads the image filesystem; it never starts it.
CID="$(docker create --network none "$IMAGE")"
docker export "$CID" > "$TMPDIR_LOCAL/rootfs.tar"
BINARY_IN_ARCHIVE="$(tar -tf "$TMPDIR_LOCAL/rootfs.tar" | awk '/(^|\/)sing-box$/ {print; exit}')"
if [ -z "$BINARY_IN_ARCHIVE" ]; then
  echo 'Could not locate sing-box in the image filesystem.' >&2
  exit 1
fi
tar -xOf "$TMPDIR_LOCAL/rootfs.tar" "$BINARY_IN_ARCHIVE" > "$TMPDIR_LOCAL/sing-box"
chmod 700 "$TMPDIR_LOCAL/sing-box"
if ! "$TMPDIR_LOCAL/sing-box" version 2>/dev/null | grep -q '^sing-box version 1\.14\.2$'; then
  echo 'Extracted binary cannot run as sing-box 1.14.2 on this host.' >&2
  exit 1
fi
install -m 0700 "$TMPDIR_LOCAL/sing-box" "$OUT"
printf 'Installed isolated test binary: %s\n' "$OUT"
"$OUT" version | head -n 2
printf 'No container started; main services and 1.12.22 unchanged.\n'
