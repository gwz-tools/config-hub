# GWZHUB deep-validation diagnostics (staging only)

## Existing production baseline (preserved)

- `cloud_verified.py` uses sing-box 1.12.22, VLESS TCP/WS/gRPC with TLS or REALITY.
- It tests genuine HTTPS requests through the tunnel (control and service URLs), with certificate validation.
- `cloud_health.py` has 24h and 7d smoothed success scoring, bounded check history, candidate rotation, and last-good publication protection.
- Public GitHub runner success is **not** Russian ISP success. Existing history has no separate Russian mobile/ISP network score.

## New diagnostic (not a production publisher)

`diagnostics/sustained.py` is an **opt-in** repeated HTTPS session tool. It starts one sing-box process for each sampled VLESS node, runs the same lightweight 204 HTTPS control repeatedly for an individually bounded window (30–1800 seconds), and reports:
- success percentage, median HTTPS latency, and maximum consecutive failures;
- timeout, TLS handshake, CA validation and selected HTTP service failure categories;
- protocol, transport, security mode and fingerprint labels (no node secrets).

Maximum 3 nodes, one node at a time, max 120 probes per node, max 64KiB per HTTPS response; no external services probed beyond the established `www.gstatic.com/generate_204` endpoint. Real throughput tests, evening timing and Russian ISP measurements remain separate acceptance tasks.

Example **on a trusted test host**, without sending any credentials to GitHub Actions logs:

```bash
python diagnostics/sustained.py --source /secure/path/nodes.txt --seconds 300 --interval 30 --max-nodes 2 --report /tmp/gwzhub-sustained.json
```

Test source must be controlled by the operator. Results are informational only and cannot change `cloud-vless.txt`.

## Compatibility and security

- Existing parser accepts VLESS REALITY/TLS with TCP, WS, and gRPC. XHTTP is **not** enabled here; requires isolated Xray version testing.
- Do not force TLS 1.2 or disable TLS 1.3.
- Do not use `allowInsecure`, `curl -k` or suppress certificate failures.
- uTLS fingerprints and SNI/ALPN are passed to sing-box per existing parser; this is not a verified matrix of client fingerprints.
- DNS failures from curl are categorized broadly; a remote DNS failure versus proxy DNS failure can require more targeted inspection. A cloud runner does not validate home-router DNS or IPv6 leakage.
- No new scheduled jobs, router changes, restart loops or external dependencies are added.
- Rollback: discard this branch/PR; no production artifact has changed.

## Remaining work

1. Run controlled 5–30 minute tests on a consented/authorized endpoint, compare peak/off-peak results with capped traffic.
2. Add tests for XHTTP with pinned Xray, and for supported fingerprint combinations per engine.
3. Establish service-specific status and DNS/path diagnostics without treating HTTP 403 as proof of VPN failure.
4. Test IPv4-only/dual-stack/IPv6-off and DNS leak behavior on actual OpenWrt routers and Android.
5. Maintain separately tagged cloud vs Russian ISP observations before enabling reliability-based promotion.
