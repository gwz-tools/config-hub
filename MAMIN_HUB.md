# Mamin → GWZHUB: private, verified, last-good source

## Verified facts, as of 2026-11-02

The [Mamin Audit status](data/mamin-audit-status.json) reports:
- **12** parser-compatible VLESS Reality candidates checked in GitHub Actions;
- **8** passed end-to-end HTTPS checks through sing-box;
- upstream RS256 signature checked using a key obtained from the exact audited
  Mamin VPN 0.9.29 APK (SHA256-pinned).

The GitHub runner is **not a Tele2/T2 probe**. These numbers will fluctuate.
The public repo intentionally contains **zero Mamin VPN credentials**.

## Architecture

Mamin upstream HTTPS `bootstrap/android-v2.json`
→ verify RSA signature with public key from exact, SHA256-pinned Android APK
→ reject expired, wrong key ID, modified payload or sequence rollback
→ parse only VLESS Reality compatible with existing cloud checker
→ test HTTPS **through each sing-box tunnel** (control, Gemini, Instagram,
Facebook, YouTube)
→ if >= 3 pass, atomically update the **private** hub file
`/opt/gwzhub/data/mamin/mamin-private-live.txt` (0600)
→ otherwise retain last good file and report safe status. A 50% drop guard
also keeps a healthy eight-node list if only three remain reachable.

This does **not** modify `verified/live-vless.txt`, `cloud-vless.txt`,
`github-candidates.txt`, any GWZHUB service/database, Podkop, or Dunay.
Deploy on **the GWZHUB Linux host only**, never on OpenWrt.

## Install once (on GWZHUB only)

SSH into GWZHUB using its existing verified SSH address. As root:

```sh
curl -fsSLo /tmp/install_mamin_hub.sh \
  https://raw.githubusercontent.com/gwz-tools/config-hub/main/install_mamin_hub.sh
sed -n '1,180p' /tmp/install_mamin_hub.sh
sh /tmp/install_mamin_hub.sh
```

The installer refuses OpenWrt and low disk space, requires installed
`python3`, `curl`, `openssl`, `sha256sum`, `sing-box`, downloads the four
Python modules, checks Python syntax, then fetches and SHA256-checks the exact
40 MB APK **once**. The APK is never run or installed on the host.
No cron entries or main services are changed.

**Run the first private source update:**

```sh
python3 /opt/gwzhub/mamin-source/mamin_hub_update.py \
  --apk-file /opt/gwzhub/data/mamin/Mamin-VPN-0.9.29.apk \
  --data-dir /opt/gwzhub/data/mamin
cat /opt/gwzhub/data/mamin/status.json
```

The updater returns a nonzero exit code on failed verification or too few
healthy tunnels and **retains** any existing private last-good feed.
Do not display or paste `mamin-private-live.txt` into logs or a public chat:
it contains credentials. Safe status contains only aggregate counts.

## Automation after a successful manual run

For regular checks every six hours, run the packaged, duplicate-safe helper
**after the first healthy status**:

```sh
sh /opt/gwzhub/mamin-source/enable_mamin_cron.sh
```

It refuses OpenWrt, requires a healthy locally checked Mamin feed and will not
add duplicate cron entries. The equivalent cron schedule is:

```cron
39 3,9,15,21 * * * /usr/bin/python3 /opt/gwzhub/mamin-source/mamin_hub_update.py --apk-file /opt/gwzhub/data/mamin/Mamin-VPN-0.9.29.apk --data-dir /opt/gwzhub/data/mamin >/dev/null 2>&1
```

Locking prevents overlapping runs. All failure/health information is stored
at `status.json`; don't redirect raw VPN URLs to logs. Timing is GWZHUB host
local time. Python path can differ; check `command -v python3`.

If there is a new APK version or signing key, **fail closed**, inspect the new
APK and establish a *new trusted hash* before updating the pin. Do not blindly
trust a replacement public key delivered in a failing catalogue.

## Plugging into the Hub's local pool

The **private** file is a source candidate input, not a publicly published
subscription. When connecting it to the installed GWZHUB collector, add
`/opt/gwzhub/data/mamin/mamin-private-live.txt` as an optional LOCAL source,
preserving the existing deduplication and health verification. Never upload
its raw links to a public GitHub branch, public Dropbox share or logs.

The installed GWZHUB collector/publisher is not part of this repository; its
source-hook location must be confirmed on GWZHUB before modifying it.
For now the standalone source is fully functional but not auto-merged into
existing public feeds. The private last-good file is ready for opt-in use.

## Security and data ownership

- HTTPS checks from GitHub or GWZHUB cannot establish mobile-operator
  whitelist-bypass reliability; verify independently on Tele2/T2.
- The private feed is intended for credentials the account is permitted to
  use. Do not redistribute third-party credentials without authorization.
- File permissions: local directory 0700, feed/status/sequence 0600.
- No unsafe "trust any certificate" or signature-verification bypass.
