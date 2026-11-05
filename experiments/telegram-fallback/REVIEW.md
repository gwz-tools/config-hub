# Mirrly TG Proxy 2.1.0 — feasibility review (no installation)

Status: **REFERENCE ONLY; NOT DEPLOYED**. No official compatibility or tunnel success is claimed.

## Source confidence
**Direct static examination performed:** Mirrly TG Proxy 2.1.0 APK (32,850,189 bytes) was located in the user's uploaded Library and unpacked as a ZIP **without running or installing it**. `assets/worker.js`: 20,781 bytes, SHA256 `5efd6e829cbc7b6f9c5be8a884b38bff23d9ddeae4e906cf39eeb6ed5e0165c5`; `assets/proton_nodes.json`: 1,527 bytes, SHA256 `905324928ed5d5fbbb3039c36ccc1b996bd9f737fa6756c4f273082e12e36349`. The worker source is examined solely as technical reference; do not copy proprietary binaries or implementation code.

## Confirmed APK findings and weaknesses

- `worker.js` exposes WebSocket endpoints `/`, `/apiws`, `/tcp`, `/tcp-v2` and diagnostic `/probe` / `/diag/port-probe`. It uses `cloudflare:sockets.connect()` with TCP readiness, separate flow-control/window and chunk settings and TCP/WebSocket teardown.
- **No authentication, per-user identity, or rate limiting appears in the examined Worker**. A destination-restricted relay can still be abused and can incur costs.
- `/probe` accepts caller-supplied destination and allowed port **without authentication** and performs actual TCP connectivity tests.
- Allowlist includes `25`, despite Cloudflare Workers' outgoing port 25 prohibition. Allowing it offers no working feature.
- Destination allowlist includes hostname suffixes; connection calls DNS resolution without proving that the resolved address still belongs to approved Telegram IPs. Not equivalent to verified target IP ownership.
- IPv6 allowlist uses string `startsWith` for prefixes; NAT64 parser is ad-hoc and supports limited spellings. Prefer canonical IP parsing and structural CIDR checks and reject ambiguous syntax; do not trust these as security boundaries.
- Write buffer upper bound `32 * 1024 * 1024` = **32 MiB** per connection, `MAX_PENDING_CHUNKS=1024`; on 128 MiB Worker memory with concurrent sessions this is significant resource-exhaustion exposure.
- Flow-controlled `/tcp-v2` uses caller-supplied `ack:<digits>`, with bounded windows of 1–8 MiB. Ack semantics and reconnection are not cryptographically authenticated or proven stable in live tests.
- The file contains claims of MTProto/SOCKS5 compatibility, but this does **not** mean a native Telegram client can consume the Worker URL. A compatible local adapter is required for its WS wire protocol.

## P1 — Telegram-only WebSocket-to-TCP fallback
- Workers can accept an incoming WebSocket and use the outbound `connect()` TCP socket API. This describes a possible WS-to-TCP bridge, not a standard Telegram proxy.
- Official Telegram clients support SOCKS5 or MTProto proxies, **not arbitrary WebSocket URLs**: https://core.telegram.org/proxy
- A Telegram native proxy configured as `server:port:secret` will not speak the Worker WebSocket framing. A purpose-built local client adapter would need to implement the protocol and bridge TCP to authenticated WS. This adds operational and security complexity, especially on Android.
- For resilience, first benchmark existing VLESS or MTProxy fallback. Avoid putting custom TCP relays in the default route.
- The current prototype **cannot forward anything**: `policy.json` has `enabled=false`, `production_ready=false`, and an empty destination allowlist.

## Cloudflare limitations (official docs checked 2026-11-05)
- Outbound TCP supported with `connect()`, but disallows certain address destinations (e.g. private and loopback, Cloudflare destinations), forbids port 25, and detects TCP loops: https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/
- Public direct inbound raw TCP not supported through a Worker URL; use HTTPS/WebSocket inbound, or Worker-to-Worker service bindings: https://developers.cloudflare.com/workers/reference/protocols/
- Free plan: 100,000 Worker requests/day, 10 ms CPU/invocation; max 128 MB memory; 6 simultaneous outgoing connections/request. Exact billable behavior depends on usage: https://developers.cloudflare.com/workers/platform/limits/
- Paid Workers start at $5/account/month; outgoing network limits/charges and features are plan-specific: https://developers.cloudflare.com/workers/platform/pricing/
- One WebSocket upgrade counts as a Worker request; connection lifetime may be long, but it is **not** an SLA or immunity from intermittent resets.

## P2 — useful engineering principles (separate from WS tunnel)
1. Wait for connection readiness before first application write; never assume outgoing TCP `connect()` is immediately writable.
2. Bound aggregate queue (e.g. <=256 KiB) and each frame (<=64 KiB); stop producers when full. Do not duplicate buffered data during reconnection.
3. Model acknowledgement and reset counters; the local reference safety module only tests arithmetic, **not network acks**.
4. Enforce connect timeout (5s example) and idle timeout (60s example) with explicit socket/WebSocket cleanup.
5. Add neutral diagnostics: connect latency, bytes sent/received, retries, timeouts, auth failures. Never log secrets, full user traffic or private URLs.
6. Test constrained networks and packet loss; only promote if measurably better than the current tunnel.

## P3 — required security before any live Worker
- Authenticate clients (rotatable credentials with server-side validation); token never in APK sources or publicly committed URL.
- Restrict destinations to explicitly verified Telegram-controlled IP ranges; reject hostnames (DNS rebinding), private IPs, IPv4-mapped IPv6, and unverified NAT64 synthesis.
- Strict port allowlist, rate limits per credential, bounded streams/queues, concurrent-session quotas and abuse monitoring.
- Treat NAT64/IPv6 format validation as an SSRF boundary: parsing an IP isn't proof it is Telegram-owned; verify and periodically revalidate origin independently.
- Keep Workers API tokens in secrets, use least privileges and budget alerts. No automatic deploy to the existing Cloudflare zone/account.
- No copying Mirrly native libs or proprietary JS.

## P4 — readiness gate / comparative tests
Run separately on at least two network conditions and devices:
- 50 connection attempts / method; report successful connections (%), connect P50/P95 (ms), timeouts and authentication failures.
- 30-minute sustained operation; report reconnects/hour, 60s+ outages and transferred bytes.
- Compare: current VLESS; existing MTProxy/TCP tunnel; proposed Worker via custom adapter (only if compatible and secured).
- Require a **measurable improvement** (e.g. 20% lower 95th-percentile connection latency *or* fewer 60s outages), without undermining VPN secrecy, before deployment.
- This audit contains **no** such measured Russian-ISP tests. No production conclusion yet.

## Embedded proton_nodes.json / DoH
`assets/proton_nodes.json` is a JSON array of **8** records (country distribution: NL 3, US 2, JP 1, PL 1, RO 1), all with port **51820**, syntactically valid IPv4 strings and base64 public keys decoding to exactly **32 bytes** (WireGuard-style public-key length). This proves only **syntax**, not authenticity, authorization, server ownership, reachability or whether the tunnel works. IP addresses and public keys are intentionally **not copied** to the repo or any subscription. No import to live pools. DoH fallback should be independently configured and leak-tested, not copied from APK.

## Decision
**Defer Worker deployment and app integration.** Continue GWZHUB's proven node verification and centralized route-feed work. Retain this isolated experiment only for later research, and do not replace existing VPN, Podkop or MTProxy paths.
