#!/usr/bin/env python3
"""Private read-only SOCKS5 VLESS probe; never print URLs, endpoints or credentials.

Tests exactly the same sing-box config as the HTTP diagnostic, but curl speaks SOCKS5.
Results are aggregate safe counters only. No live services or private feeds modified.
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
from cloud_verified import CONTROL_URL, SERVICE_URLS, parse_vless, unique_candidates

DEFAULT_BIN = "/opt/gwzhub/mamin-source/bin/sing-box-1.14.2"
DEFAULT_POOL = "/opt/gwzhub/output/live-vless.txt"


def safe_error(blob):
    """Fixed error categories only; never return raw error messages."""
    msg = blob.lower()
    labels = []
    for label, strings in (
        ("reality_key", (b"public_key", b"short_id", b"reality")),
        ("tls", (b"tls", b"certificate", b"handshake")),
        ("deprecated", (b"deprecated", b"removed", b"unsupported")),
        ("invalid_field", (b"unknown field", b"invalid", b"missing")),
        ("timeout", (b"timeout", b"deadline exceeded")),
        ("eof_reset", (b"eof", b"reset", b"broken pipe")),
        ("dns", (b"no such host", b"lookup", b"dns")),
        ("other", (b"permission denied", b"outbound not found")),
    ):
        if any(x in msg for x in strings):
            labels.append(label)
    return labels or ["unclassified"]


def probe_socks(port, url, timeout=10):
    cmd = [
        "curl", "-4", "--silent", "--show-error", "--noproxy", "",
        "--socks5-hostname", f"127.0.0.1:{port}",
        "--connect-timeout", "4", "--max-time", str(timeout),
        "--output", os.devnull, "--write-out", "%{http_code}", url
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=timeout+3)
        return proc.returncode, int(proc.stdout.strip()) if proc.stdout.strip().isdigit() else 0
    except (subprocess.TimeoutExpired, OSError):
        return 124, 0


def check_link(link, binary):
    result = Counter()
    try:
        outbound = parse_vless(link)
    except (ValueError, TypeError):
        result["parser_rejected"] += 1
        return result

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    cfg = {
        "log": {"level": "warn"},
        "inbounds": [{"type": "mixed", "tag": "local",
                       "listen": "127.0.0.1", "listen_port": port}],
        "outbounds": [outbound],
        "route": {"final": "proxy"}
    }
    with tempfile.TemporaryDirectory(prefix="gwzhub-socks-private-") as directory:
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        os.chmod(path, 0o600)
        try:
            check = subprocess.run([binary, "check", "-c", str(path)],
                                   capture_output=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            result["config_check_process_error"] += 1
            return result
        if check.returncode:
            result["config_rejected"] += 1
            for reason in safe_error(check.stdout + check.stderr):
                result["config_" + reason] += 1
            return result
        result["config_accepted"] += 1

        with (Path(directory) / "singbox.log").open("wb") as logfile:
            os.chmod(logfile.name, 0o600)
            try:
                process = subprocess.Popen([binary, "run", "-c", str(path)],
                                           stdin=subprocess.DEVNULL,
                                           stdout=logfile, stderr=logfile,
                                           start_new_session=True)
            except OSError:
                result["proxy_start_failed"] += 1
                return result
        try:
            ready = False
            for _ in range(30):
                if process.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.1)
            if not ready:
                result["proxy_not_ready"] += 1
                return result
            result["proxy_ready"] += 1

            code, http = probe_socks(port, CONTROL_URL)
            result[f"socks_control_curl_exit_{code}"] += 1
            if not (code == 0 and 200 <= http < 400):
                result["socks_control_failed"] += 1
                return result
            result["socks_control_https_ok"] += 1

            all_ok = True
            for name, url in SERVICE_URLS.items():
                exitcode, status = probe_socks(port, url, timeout=9)
                if exitcode == 0 and 200 <= status < 400:
                    result[f"service_{name}_ok"] += 1
                else:
                    result[f"service_{name}_failed"] += 1
                    all_ok = False
            if all_ok:
                result["strict_socks_end_to_end_pass"] += 1
        finally:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-file", type=Path, default=Path(DEFAULT_POOL))
    parser.add_argument("--sing-box", default=DEFAULT_BIN)
    parser.add_argument("--max-candidates", type=int, default=6)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run with sudo: credentials must stay private")
    if not 1 <= args.max_candidates <= 20:
        parser.error("max-candidates must be 1..20")
    if not Path(args.sing_box).is_file():
        parser.error("Isolated sing-box not found")
    os.umask(0o077)
    links = unique_candidates(args.control_file, args.max_candidates)
    counts = Counter()
    for link in links:
        counts["checked"] += 1
        counts.update(check_link(link, args.sing_box))
    print(json.dumps({
        "method": "SOCKS5 hostname; local independent sing-box",
        "pool": "locally supplied existing VLESS list",
        "total_candidates": len(links),
        "stage_counts_only": dict(sorted(counts.items())),
        "credentials_printed": False,
        "live_services_changed": False,
        "feeds_changed": False
    }, indent=2))

if __name__ == "__main__":
    main()
