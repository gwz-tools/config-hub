# GWZHUB routing — Stage 2 (staged, not deployed)

This is a new **additive** module. Existing Podkop, GWZHUB and GitHub feed workflows are untouched.

## Source of truth and limitations
- `routing/policy.json` is a **draft**, NOT a full replacement for the Dunay/Zorik ~144 DIRECT-domain list.
- The exact existing router list must be exported and merged before deployment. Do not silently synthesize it.
- `review_direct_candidates` are not active DIRECT entries. Verify provider ownership, application requests, CDN dependencies, DNS behavior and collisions first.
- IP-check services must continue through PROXY unless explicitly decided otherwise.
- No TLD / GeoIP-based blanket DIRECT. Matching is apex + subdomains on a DNS-label boundary.
- Default for unknown public domains is PROXY.
- Priority: **most-specific DNS suffix wins**, with duplicate exact suffix assigned to different actions rejected. For equal specificity, only one action may exist. BLOCK/PROXY/DIRECT entries therefore require explicit review if a parent suffix changes.
- Local subnet/IP bypass, DNS route selection and IPv6 leak protections are client implementation requirements, not implied by this domain-only draft.
- Domain policy does not override actual socket routing for IP-only connections. CDN/shared IP routing requires client-side domain-aware handling.

## Important upstream classification
`igareck/vpn-configs-for-russia/WHITE-CIDR-RU-all.txt` is currently a **VLESS subscription** (contains `vless://` lines), *not* a list of CIDR networks. Its `CIDR` label describes the intended white-list operation mode. It must not enter DIRECT IP routes. The parser in `routing/build.py` rejects such imports. Mirror URLs must be checked by content + provenance, never treated as trusted just because they return HTTP 200.

## Build & tests
```sh
python routing/build.py --out /tmp/gwz-routing-generated
python -m unittest discover -s tests -p test_routing_policy.py -v
```

Output:
- `rules.json`: normalized staged rules with deterministic suffix precedence
- `direct.txt`, `proxy.txt`, `block.txt`: staging-only domain lists
- `review.txt`: proposed new domains requiring evidence before DIRECT

Do not insert these files directly into Podkop or Android until exact legacy DIRECT import, overlapping rule review, DNS handling, and device-level tests have passed.

## Rollback
No production modification has been made. Discard this branch/PR to revert the proposal. Existing `main` and `verified` outputs remain unchanged.

## Next
1. Import exact Dunay/Zorik current DIRECT domain lists from UCI/backups, retain provenance.
2. Verify 17 candidate domains by dependency ownership and test both direct and tunnel traffic.
3. Add separate **real CIDR** feeds only after confirming contents are valid IPv4/IPv6 networks; never auto-DIRECT by source name.
4. Compile equivalent policy for sing-box Android and Podkop in their supported formats; test rule order, DNS and failover.
5. Address outdated `fast.txt` candidate publishing separately; do not conflate with `cloud-vless.txt` (actual tunnel-tested).
