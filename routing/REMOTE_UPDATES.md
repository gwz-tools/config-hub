# GWZHUB: centrally managed routing rules (Stage 2 contract)

## Source of truth (editable in GitHub)
- `routing/confirmed-direct-20261105.txt`: explicit DIRECT destinations.
- `routing/confirmed-proxy-20261105.txt`: explicit PROXY destinations.
- Each line is one DNS suffix, apex + subdomains. Add/remove/edit a line in GitHub, open PR, run tests.
- Existing `routing/policy.json` review candidates are **not automatically promoted**. Conflicting / overlapping DIRECT and PROXY domains fail the build; no automatic preference.

**Crucial:** These lists are currently in an **unmerged experimental PR branch**, NOT published to stable URLs and NOT loaded by any device. Until a stable release and client integration, changing text does NOT update router/app behavior.

## Build format

```bash
python routing/publish_bundle.py --output /tmp/gwzhub-routing-bundle
```

The builder emits:
- `manifest.json`: deterministic content-version SHA prefix, per-file SHA256, sizes, recommended refresh schedule;
- `direct.txt`, `proxy.txt`, `block.txt`: readable lists;
- `direct.rule-set.json`, `proxy.rule-set.json`, `block.rule-set.json`: sing-box **v3 source** sets.

No IP/CIDR guesses, no DNS config, no VPN keys. It does **not** commit, deploy or publish. For a future release, publish a complete verified **immutable versioned directory**, then atomically move the stable manifest pointer. Do not replace existing subscription URLs.

## Android update algorithm (to implement in the Android app project)

1. On first launch load a bundled **last-known-good** policy. Make routing work offline.
2. Fetch small manifest on cold start only if previous check older than e.g. **6h**; background check every **6h** with jitter, on metered/battery-save connections less aggressively. Avoid constant polling.
3. Use HTTPS, ordinary TLS certificate validation, conditional HTTP `If-None-Match` (ETag) / 304 if server supports it, and a 5–10s timeout. Honor backoff after network failures.
4. If version unchanged: keep cache, no reload. If changed: download ALL required files (only from a pinned HTTPS origin or approved mirror), cap bytes, validate SHA256, version/schema and mutual exclusion; optionally compile binary rule-sets with actual installed client engine. Keep old set active while doing so.
5. Activate **DIRECT and PROXY together**, atomically swap the entire known-good policy and persist previous version. If any failure, retain old policy and log a reason. Never activate half a bundle.
6. If VPN is unavailable, mandatory PROXY destinations must **not** fall back to DIRECT. That requires a system-wide tunnel / per-app kill switch in the actual client; `*.txt` alone cannot provide this guarantee.
7. Show policy version, last-check timestamp, last-apply timestamp, source, and actionable refresh/error UI. Let user request manual refresh.
8. If app handles manually entered domain overrides, keep local edits in a separate overlay and detect/report conflicts on update; never silently erase user changes.

For Android, a **six-hour check** plus one check on launch if stale is a reasonable default, NOT a request on every launch. A node subscription and routing policy are separate resources; receiving new VLESS links does not update domain routing by itself.

## OpenWrt / Podkop integration

- sing-box supports `route.rule_set` with `type: remote`, `url`, `format`, `update_interval`; remote caches need `experimental.cache_file.enabled`. In sing-box **1.12.22** remote download can be configured with `download_detour`; in newer versions the HTTP client mechanism differs. Review version before applying.
- A remote rule-set defines **matches**, not whether traffic should use DIRECT or PROXY. Attach each rule-set to the proper routing section and guarantee precedence.
- Podkop may manage its own downloader/ruleset mechanism; do **not** paste a full sing-box config or overwrite generated files. When safely supported, reference a stable release URL, for example `.../routing/releases/<VERSION>/direct.rule-set.json` (illustrative, not a currently live URL).
- For other routers that do not support remote rules, copy `direct.txt` / `proxy.txt` manually; backup and compare before apply.
- Do not make download depend solely on the tunnel it configures; keep a safe bootstrap path and local cache.

## Server publication strategy

Create a **separate release workflow** with human review and `contents: write` permission only for publishing validated, immutable rule snapshots. Verify all hashes and files before moving the stable manifest reference. Keep 2–3 prior versions for rollback. The present workflow is **read-only** and publishes nothing; no existing feeds or GitHub automation are touched.

For safety, avoid a small mutable GitHub raw URL being the only source of truth for a high-risk kill-switch: pin an operator-controlled origin and add signature verification for untrusted mirrors later. SHA256 alone checks transfer consistency if the manifest is trusted; it does not authenticate a compromised publisher.

## Rollback

Restore the previous manifest/version and complete cached bundle atomically. Record the old/new versions; never replace a good policy with an empty or partially downloaded list.
