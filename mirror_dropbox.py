#!/usr/bin/env python3
"""Optional Dropbox mirror for the cloud VLESS feed.

All OAuth credentials MUST be GitHub Actions secrets, not tracked repo files.
Without credentials, the mirror is skipped and the primary feed is unaffected.
"""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def upload(source: Path, dest: str):
    key = os.getenv("GWZ_DROPBOX_APP_KEY", "").strip()
    secret = os.getenv("GWZ_DROPBOX_APP_SECRET", "").strip()
    refresh = os.getenv("GWZ_DROPBOX_REFRESH_TOKEN", "").strip()
    if not (key and secret and refresh):
        print("Dropbox mirror skipped: three required GitHub secrets are not configured")
        return False
    if not dest.startswith("/") or ".." in dest.split("/"):
        raise ValueError("Invalid Dropbox destination path")
    lines = [x.strip() for x in source.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(lines) < 3 or any(not x.startswith("vless://") for x in lines):
        raise ValueError("Dropbox mirror rejected: source lacks at least 3 VLESS nodes")
    token_body = urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": key,
        "client_secret": secret,
    }).encode("utf-8")
    req = Request("https://api.dropboxapi.com/oauth2/token", data=token_body,
                  headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(req, timeout=20) as resp:
        token = json.load(resp)["access_token"]
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    args = json.dumps({"path": dest, "mode": "overwrite",
                       "autorename": False, "mute": True}, separators=(",", ":"))
    req = Request("https://content.dropboxapi.com/2/files/upload", data=payload, method="POST",
                  headers={
                      "Authorization": "Bearer " + token,
                      "Dropbox-API-Arg": args,
                      "Content-Type": "application/octet-stream",
                  })
    with urlopen(req, timeout=30) as resp:
        result = json.load(resp)
    print("Dropbox mirror written:", result.get("path_display", dest),
          "VLESS entries:", len(lines))
    return True


if __name__ == "__main__":
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "cloud-vless.txt")
    path = os.getenv("GWZ_DROPBOX_PATH", "/GWZHUB/cloud-vless.txt")
    upload(source, path)
