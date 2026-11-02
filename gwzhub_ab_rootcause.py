#!/usr/bin/env python3
"""Isolated no-secret GWZHUB VLESS root-cause diagnostic.

No publication, cron, firewall, routing or live service changes.
Reports only fixed-category counters, no endpoint, UUID, config, or raw logs.
"""
import argparse
from collections import Counter
from contextlib import suppress
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, "/opt/gwzhub/mamin-source")
from cloud_verified import parse_vless, unique_candidates

TEST_URL = "https://www.gstatic.com/generate_204"
BIN_DEFAULT = "/opt/gwzhub/mamin-source/bin/sing-box-1.14.2"


def classify_static(blob):
    """Only predetermined category labels; never emit arbitrary log text."""
    s = blob.lower()
    groups = {
        "flow_option": [b"flow", b"vision"],
        "reality_parameter": [b"short_id", b"short id", b"public_key", b"public key", b"reality"],
        "tls": [b"tls", b"handshake", b"certificate", b"x509", b"ech", b"utls"],
        "unsupported_or_deprecated": [b"unsupported", b"deprecated", b"removed"],
        "invalid_config": [b"invalid", b"unknown field", b"missing", b"unrecognized"],
        "timeout": [b"timeout", b"deadline exceeded"],
        "reset_or_eof": [b"connection reset", b"broken pipe", b"unexpected eof"],
        "dns": [b"no such host", b"lookup", b"dns"],
        "connection_refused": [b"connection refused", b"connect: refused"],
        "bad_request": [b"bad request", b"wrong version number"],
        "permission": [b"permission denied", b"operation not permitted"],
    }
    return [key for key, patterns in groups.items() if any(x in s for x in patterns)] or ["unclassified"]


def port_free():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def https_probe(port=None):
    command = [
        "curl", "-4", "--silent", "--show-error", "--verbose",
        "--connect-timeout", "4", "--max-time", "12",
        "--output", os.devnull, "--write-out", "%{http_code}",
    ]
    if port is None:
        command += ["--noproxy", "*"]
    else:
        command += ["--noproxy", "", "--proxy", f"http://127.0.0.1:{port}"]
    command += [TEST_URL]
    try:
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=16, check=False)
        code = int(p.stdout.strip()) if p.stdout.strip().isdigit() else 0
        # curl's verbose tracing can include secrets for other URLs: never print it.
        trace = p.stderr.lower()
        result = {"curl_exit": p.returncode, "http_status": code}
        if port is not None:
            result["proxy_connect_200"] = (
                b"200 connection established" in trace or
                b"200 connection established" in trace.replace(b"\\r", b"")
            )
        if p.returncode:
            result["failure_categories"] = classify_static(trace)
        return result
    except (OSError, subprocess.TimeoutExpired):
        return {"curl_exit": 124, "http_status": 0, "failure_categories": ["process_error"]}


def run_one(binary, outbound):
    result = {}
    p = port_free()
    config = {
        "log": {"level": "debug"},
        "inbounds": [{"type": "mixed", "tag": "local", "listen": "127.0.0.1", "listen_port": p}],
        "outbounds": [outbound],
        "route": {"final": outbound["tag"]},
    }
    with tempfile.TemporaryDirectory(prefix="gwz-ab-rootcause-") as tmp:
        config_file = Path(tmp) / "config.json"
        log_file = Path(tmp) / "singbox.log"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        os.chmod(config_file, 0o600)
        try:
            check = subprocess.run([binary, "check", "-c", str(config_file)],
                                   capture_output=True, timeout=12, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {"config_check": "process_error"}
        if check.returncode:
            return {
                "config_check": "rejected",
                "config_failure_categories": classify_static(check.stderr + check.stdout),
            }
        result["config_check"] = "accepted"
        with log_file.open("wb") as logs:
            os.chmod(log_file, 0o600)
            try:
                proc = subprocess.Popen([binary, "run", "-c", str(config_file)],
                                        stdin=subprocess.DEVNULL, stdout=logs,
                                        stderr=logs, start_new_session=True)
            except OSError:
                return {"config_check": "accepted", "proxy": "cannot_start"}
        try:
            ready = False
            for _ in range(30):
                if proc.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", p), timeout=0.2):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.1)
            result["proxy"] = "ready" if ready else "not_ready"
            if ready:
                result["https"] = https_probe(p)
        finally:
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
            with suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=3)
            if proc.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            try:
                log = log_file.read_bytes()
                # The VLESS plugin sometimes emits handshake errors at info or debug level.
                result["singbox_log_categories"] = classify_static(log)
            except OSError:
                pass
    return result


def summary(rows):
    c = Counter()
    for row in rows:
        c["checked"] += 1
        c["config_" + row.get("config_check", "unknown")] += 1
        if "config_failure_categories" in row:
            for kind in row["config_failure_categories"]:
                c["reject_" + kind] += 1
        if row.get("proxy") == "ready":
            c["proxy_ready"] += 1
        h = row.get("https")
        if h:
            c["https_curl_exit_" + str(h["curl_exit"])] += 1
            if 200 <= h["http_status"] < 400:
                c["https_ok"] += 1
            if h.get("proxy_connect_200"):
                c["proxy_connect_200"] += 1
            for kind in h.get("failure_categories", []):
                c["curl_" + kind] += 1
        for kind in row.get("singbox_log_categories", []):
            c["singbox_" + kind] += 1
    return dict(sorted(c.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-file", type=Path, default=Path("/opt/gwzhub/output/live-vless.txt"))
    ap.add_argument("--sing-box", default=BIN_DEFAULT)
    ap.add_argument("--max-candidates", type=int, default=6)
    args = ap.parse_args()
    if not 1 <= args.max_candidates <= 10:
        ap.error("max-candidates must be 1..10")
    if os.geteuid() != 0:
        ap.error("run as root to protect in-memory credentials and temporary files")
    if not Path(args.sing_box).is_file():
        ap.error("sing-box binary unavailable")
    os.umask(0o077)
    control = https_probe()
    direct = run_one(args.sing_box, {"type": "direct", "tag": "direct"})
    results = []
    links = unique_candidates(args.control_file, args.max_candidates)
    for link in links:
        try:
            out = parse_vless(link)
            results.append(run_one(args.sing_box, out))
        except (ValueError, TypeError):
            results.append({"config_check": "parser_rejected"})
    print(json.dumps({
        "diagnostic": "sing-box local direct versus VLESS",
        "direct_https": control,
        "local_singbox_direct_https": direct.get("https"),
        "local_singbox_direct_config": direct.get("config_check"),
        "local_singbox_direct_proxy": direct.get("proxy"),
        "local_singbox_direct_log_categories": direct.get("singbox_log_categories", []),
        "vless_totals_only": summary(results),
        "credentials_printed": False,
        "main_services_changed": False,
        "firewall_or_routes_changed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
