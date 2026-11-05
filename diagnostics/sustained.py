#!/usr/bin/env python3
"""Bounded opt-in sustained HTTPS validation through one VLESS tunnel.

No changes to production subscriptions, health ledger or routing. Only an explicitly
provided source file is tested. Reports contain hashed identities, not credentials.
Github runner measurements must never be labelled 'Russian ISP'.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

from cloud_verified import CONTROL_URL, parse_vless, public_endpoint, tcp_probe

MAX_DURATION = 1800
MAX_REQUESTS = 120
MAX_NODES = 3
MAX_WORKERS = 1
MAX_TRANSFER_BYTES = 65536
ERRORS = {
    5: "proxy_dns_failure",
    6: "dns_failure",
    7: "connect_failure",
    16: "http2_transport_error",
    18: "partial_transfer",
    28: "timeout",
    35: "tls_handshake_failure",
    47: "redirect_limit",
    52: "empty_reply",
    55: "send_failure",
    56: "connection_reset_or_read_failure",
    60: "certificate_validation_failure",
    77: "ca_certificate_failure",
    92: "http2_stream_failure",
}


def identity(line):
    return hashlib.sha256(line.split("#", 1)[0].encode()).hexdigest()


def transport_metadata(link):
    parsed = urlsplit(link)
    q = parse_qs(parsed.query, keep_blank_values=True)
    get = lambda k, default="": q.get(k, [default])[0]
    transport = get("type", "tcp")
    if transport == "raw":
        transport = "tcp"
    return {"protocol": "vless", "security": get("security", "none"),
            "transport": transport, "fingerprint": get("fp", ""),
            "alpn": get("alpn", "")}


def classify(exit_code, http_code):
    if exit_code:
        return ERRORS.get(exit_code, "proxy_or_transport_failure")
    if 200 <= http_code < 400:
        return "success"
    if http_code in (401, 403, 407, 429, 451):
        return "service_specific_http_rejection"
    if 400 <= http_code < 600:
        return "service_http_error"
    return "unexpected_http_response"


def probe(proxy_port, timeout=10, url=CONTROL_URL):
    """Explicit proxy: no DIRECT fallback, no response body, no redirects."""
    timeout = max(2, min(15, int(timeout)))
    command = [
        "curl", "--silent", "--show-error", "--noproxy", "",
        "--connect-timeout", "3", "--max-time", str(timeout),
        "--max-filesize", str(MAX_TRANSFER_BYTES),
        "--output", os.devnull, "--write-out",
        "%{http_code} %{time_total} %{size_download}",
        "--proxy", f"http://127.0.0.1:{proxy_port}", url,
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, timeout=timeout + 2,
                                check=False)
        values = result.stdout.strip().split()
        code = int(values[0]) if values and values[0].isdigit() else 0
        latency = float(values[1]) if len(values) > 1 else None
        size = float(values[2]) if len(values) > 2 else 0
        if size > MAX_TRANSFER_BYTES:
            return {"ok": False, "reason": "download_limit_exceeded", "http_status": code}
        reason = classify(result.returncode, code)
        return {"ok": reason == "success", "reason": reason, "http_status": code,
                "latency_ms": round(latency * 1000) if latency is not None else None}
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return {"ok": False, "reason": "probe_execution_failure", "http_status": 0}


def spawn_and_test(link, sing_box, seconds, interval):
    outbound = parse_vless(link)  # strict existing support; never loosen TLS
    endpoint = public_endpoint(outbound["server"], outbound["server_port"])
    if not endpoint:
        return {"error": "no_public_dns_endpoint", "observations": []}
    if not tcp_probe(endpoint):
        return {"error": "tcp_unreachable", "observations": []}
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    config = {
        "log": {"level": "error"},
        "inbounds": [{"type": "mixed", "tag": "local",
                      "listen": "127.0.0.1", "listen_port": port}],
        "outbounds": [outbound],
        "route": {"final": "proxy"},
    }
    with tempfile.TemporaryDirectory(prefix="gwz-sustain-") as directory:
        cfg = Path(directory) / "config.json"
        cfg.write_text(json.dumps(config), encoding="utf-8")
        check = subprocess.run([sing_box, "check", "-c", str(cfg)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False)
        if check.returncode:
            return {"error": "sing_box_schema_rejected", "observations": []}
        proc = subprocess.Popen([sing_box, "run", "-c", str(cfg)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        rows = []
        try:
            ready = False
            for _ in range(30):
                if proc.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=.2):
                        ready = True
                        break
                except OSError:
                    time.sleep(.1)
            if not ready:
                return {"error": "local_core_failed", "observations": []}
            deadline = time.monotonic() + seconds
            while len(rows) < MAX_REQUESTS and time.monotonic() < deadline:
                if proc.poll() is not None:
                    rows.append({"ok": False, "reason": "local_core_exited", "http_status": 0})
                    break
                rows.append(probe(port, timeout=min(10, max(2, interval))))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(interval, remaining))
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=2)
        return {"error": None, "observations": rows}


def summarize(link, result):
    entries = result["observations"]
    success = sum(x["ok"] for x in entries)
    latencies = sorted(x["latency_ms"] for x in entries
                       if x["ok"] and x.get("latency_ms") is not None)
    reason_counts = {}
    for x in entries:
        reason_counts[x["reason"]] = reason_counts.get(x["reason"], 0) + 1
    consecutive = 0
    worst = 0
    for x in entries:
        consecutive = 0 if x["ok"] else consecutive + 1
        worst = max(worst, consecutive)
    return {
        "id": identity(link), "transport": transport_metadata(link),
        "samples": len(entries), "successes": success,
        "success_pct": round(100 * success / len(entries), 2) if entries else None,
        "median_https_ms": latencies[len(latencies)//2] if latencies else None,
        "max_consecutive_failures": worst, "reasons": reason_counts,
        "error": result["error"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sing-box", default="sing-box")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--max-nodes", type=int, default=2)
    parser.add_argument("--report", type=Path, default=Path("/tmp/gwzhub-sustained.json"))
    args = parser.parse_args()
    if not 30 <= args.seconds <= MAX_DURATION or not 5 <= args.interval <= 300:
        parser.error("Duration must be 30-1800 s and interval 5-300 s")
    if not 1 <= args.max_nodes <= MAX_NODES:
        parser.error("max-nodes must be 1-3")
    links = [line.strip() for line in args.source.read_text(encoding="utf-8").splitlines()
             if line.strip().startswith("vless://")]
    if not links:
        parser.error("No VLESS candidates in source")
    # Independent audit only, never promotes nodes to production feed.
    reports = []
    for line in links[:args.max_nodes]:
        try:
            report = summarize(line, spawn_and_test(line, args.sing_box,
                                                    args.seconds, args.interval))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report = summarize(line, {"error": type(exc).__name__, "observations": []})
        reports.append(report)
    payload = {"vantage": "github_runner_or_operator_specify_externally",
               "verified_in_russia": False,
               "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "duration_seconds_per_node": args.seconds,
               "interval_seconds": args.interval,
               "nodes": reports}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"nodes": len(reports), "samples": sum(x["samples"] for x in reports),
                      "credentials_logged": False}))


if __name__ == "__main__":
    main()
