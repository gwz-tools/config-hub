# Mamin VPN catalogue import (audited source, not a public feed)

## Current status
The Mamin source is integrated in a **separate, fail-closed audit pipeline**.
It does not change `cloud-vless.txt`, `verified/live-vless.txt`, current
GWZHUB services, databases or Podkop settings.

The importer was recovered from an earlier GWZHUB research file and uses
a public RS256 verification key pinned from Mamin VPN Android 0.9.29.
The authenticity of a signed payload is not proof that its endpoints work
or that the service author permits public redistribution of credentials.

## Security checks
- Requires HTTPS to fetch the upstream bootstrap-v2 catalogue.
- Checks pinned public key, signature, algorithm and key ID.
- Checks expected package/schema, issuance and expiry timestamps.
- Rejects sequence rollback and reuse with altered payload **when the local
  sequence state is retained**. The GitHub-hosted weekly audit is ephemeral;
  sequence continuity is enforced on a persistent GWZHUB installation only.
- Deduplicates valid VLESS/Trojan/Shadowsocks URLs; only VLESS Reality
  candidates feed the existing VLESS parser.
- Rejects catalogues with invalid signature, expired timestamps or no
  relevant candidates.
- Never adds credentials to GitHub tracked files, artifacts or logs.

## Triggering and outputs

Actions → **Mamin VPN signed catalogue audit** → Run workflow.
There is also a weekly read-only audit on Monday 04:39 UTC.

The audit downloads into `$RUNNER_TEMP/mamin`, prints counts only,
and removes raw links afterward. The cloud parser confirms syntax and public routability constraints. Then
`mamin_probe.py` starts isolated sing-box tunnels and attempts the same
real HTTPS checks as the existing cloud verifier (control URL, Gemini,
Instagram, Facebook, YouTube). Only aggregate counts are printed.
A successful GitHub-runner probe is **not proof of access from Tele2/T2**.

For trusted private GWZHUB local use (persistent sequence tracking):

```sh
python3 mamin_verify_import.py --output-dir /opt/gwzhub/data
```

Requirements: Python 3 and `openssl` on PATH. This emits
`mamin-vless-reality.verified.txt` for testing by the existing checker.
Do not commit this output or store private subscription links in public GitHub.

## Next gate before any automatic publication
1. Confirm fresh Mamin catalogue is reachable and RS256 verification passes.
2. Confirm HTTPS works **through** each VLESS tunnel with `cloud_verified.py`
   or the GWZHUB checker, not merely TCP reachability.
3. Verify authorization to redistribute any source's credentials.
4. Publish only if enough working nodes pass, preserving the last-good list;
   never let an empty Mamin result overwrite an existing feed.
5. Confirm operation on the intended mobile ISP separately from GitHub runner.

No live subscription or router configuration changes are made by this audit.
