# Stage 2 production gate — exact Podkop exclusions and DNS checks

**Status:** safe staging; not enabled on routers, Android or production subscription feeds.
This document prevents outdated historical lists from being mistaken for live router state.

## 1. Export only the DIRECT-domain text

On each router, run commands locally via SSH and save the **output only**.
Do not export `uci show podkop`, `/etc/config/podkop`, `/etc/sing-box/config.json` or subscription links: these may contain credentials.

```sh
uci -q get podkop.ru_apps.connection_type
uci -q get podkop.ru_apps.user_domain_list_type
uci -q get podkop.ru_apps.user_domains_text
```

The first line should indicate `exclusion`, second normally `text`. If section names differ, discover with:
```sh
uci -q show podkop | grep -E '^podkop\.[^.]+=section$'
```
Then inspect `connection_type` for each listed section, and export only its `user_domains_text`. An empty output is not proof of an empty rule set: inspect local/remote/community domain list settings separately.

Keep separate sanitized UTF-8 files: `dunay.txt`, `zorik.txt`, `r3p.txt` (the names are labels, not a command to publish router addresses). On Windows, PowerShell `Out-File -Encoding utf8` may add a BOM; the importer accepts it.

## 2. Compare all sources — no silent union deployment

```sh
python routing/import_podkop.py --source dunay=dunay.txt zorik=zorik.txt r3p=r3p.txt --output /tmp/gwz-direct-audit.json
```

The JSON report includes per-source counts, exact domains, SHA256 of normalized lists, common and union, and explicit `missing_by_source` differences. It is not a production artifact. If differences exist, identify intentional per-router exceptions before choosing a canonical baseline.

The historic counts of about 144, 76/77 and 186 from earlier sessions are **not** a substitute for current exports.

## 3. Ruleset files, never full client DNS/routing configurations

```sh
python routing/export_ruleset.py --output /tmp/gwz-rulesets
```

Outputs `direct-domains.rule-set.json`, `proxy-domains.rule-set.json`, and `block-domains.rule-set.json` in sing-box version 3 format. They contain only domain matches and no DNS, keys or outbound configuration. Matching domain rules are attached to the right Podkop sections: DIRECT -> Exclusion, PROXY -> Proxy, BLOCK -> Block.

These default outputs are **staging only**. The `--validated-legacy` option refuses mismatched or undersized historical exports; it is not a shortcut around manual review.

Never point Podkop at the branch output as a live ruleset until it is generated from verified canonical data, tested with the router's installed sing-box and staged as a separate new section. Avoid overwriting an existing working exclusion.

## 4. Router-level DNS and IPv6 go/no-go

Perform both with VPN up **and** deliberately down, and after Wi-Fi/cellular/WAN reconnect:
- `uci -q get podkop.settings.dns_type` and `uci -q get podkop.settings.dns_server` for intended DNS type/address. Option names differ by version; missing values are not evidence of a particular resolver.
- `nslookup example.com 127.0.0.1`, plus a Russian DIRECT hostname and a foreign PROXY hostname, then compare actual DNS traffic on WAN to ensure no unintended ISP DNS requests (requires packet capture/traffic observation).
- Inspect `/etc/sing-box/config.json` **only on router**, without uploading it, to confirm DNS detour, route priority, FakeIP handling, IPv4/IPv6 strategy and direct LAN exemptions.
- Confirm `ifconfig.me` / `ipify.org` are not forced DIRECT. Check both IPv4 and IPv6 exit (where IPv6 available). A single IP-check page does not prove DNS-leak protection.
- When downloading rule sets through Proxy/VPN, keep local/last-good lists and allow recovery with direct download if the tunnel fails. Never introduce a circular bootstrap dependency.

**No hardware change is approved by offline rule-set compilation alone.**

## 5. Atomic rollout / rollback

Before changing a router, store a dated secure backup of /etc/config/podkop and actual user-domain list locally. Test first on one noncritical device. After applying a new list, verify route priority, DNS leakage, service-specific functionality, VPN-down LAN/DIRECT operation, and reboot persistence. If a check fails, restore the saved file and reload Podkop; never keep a broken rule set active.

Any public GitHub feed must contain only non-secret rule data, never private VPN subscription URLs or credentials.
