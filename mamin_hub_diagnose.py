#!/usr/bin/env python3
"""Read-only, private stage-by-stage Mamin connectivity diagnostic.

DO NOT print endpoints, UUIDs, VLESS URIs, configuration or catalogue bytes.
Does not modify the private last-good list, its sequence state, cron or router.
"""
import argparse
from collections import Counter
from contextlib import suppress
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

# Can run from /tmp after downloading, with modules already privately installed.
sys.path.insert(0, "/opt/gwzhub/mamin-source")
from cloud_verified import (CONTROL_URL, SERVICE_URLS, http_probe,
                            parse_vless, public_endpoint, tcp_probe,
                            unique_candidates)


def reachable_addresses(hostname, port, timeout=2):
    """Try each public address independently; do not leak addresses."""
    results = {"ipv4": False, "ipv6": False}
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        return results
    for entry in addresses:
        address = entry[4]
        try:
            if not ipaddress.ip_address(address[0]).is_global:
                continue
            family = "ipv4" if entry[0] == socket.AF_INET else "ipv6"
            if family not in results or results[family]:
                continue
            with socket.socket(entry[0], socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(address)
            results[family] = True
        except (OSError, ValueError):
            pass
    return results


def curl_probe(proxy_port, url, timeout=10):
    """Return only curl numeric exit status and numeric HTTP code; discard stderr."""
    command = [
        "curl", "--silent", "--show-error", "--noproxy", "",
        "--connect-timeout", "3", "--max-time", str(timeout),
        "--output", os.devnull, "--write-out", "%{http_code}",
        "--proxy", f"http://127.0.0.1:{proxy_port}", url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout + 3, check=False)
        http_code = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        return result.returncode, http_code
    except subprocess.TimeoutExpired:
        return 124, 0
    except OSError:
        return 127, 0


def classify_run_errors(path):
    """Classify locally captured sing-box errors without printing their text."""
    try:
        content = path.read_bytes().lower()
    except OSError:
        return []
    rules = (
        ("singbox_error_timeout", (b"timeout", b"deadline exceeded")),
        ("singbox_error_connection_reset", (b"connection reset",)),
        ("singbox_error_connection_refused", (b"connection refused",)),
        ("singbox_error_network_unreachable", (b"network is unreachable", b"no route to host")),
        ("singbox_error_tls_or_reality", (b"tls", b"reality", b"handshake")),
        ("singbox_error_eof", (b"unexpected eof",)),
        ("singbox_error_dns", (b"lookup", b"no such host")),
    )
    return [name for name, patterns in rules if any(p in content for p in patterns)]


def inspect_one(link, sing_box):
    counters = Counter()
    try:
        outbound = parse_vless(link)
    except (ValueError, TypeError):
        counters["parser_rejected"] += 1
        return counters
    endpoint = public_endpoint(outbound["server"], outbound["server_port"])
    if endpoint is None:
        counters["dns_or_no_global_ip"] += 1
        return counters
    counters["dns_ok"] += 1

    # Crucial: compare existing checker's FIRST DNS address to all addresses.
    addresses = reachable_addresses(outbound["server"], outbound["server_port"])
    if addresses["ipv4"]:
        counters["ipv4_tcp_ok"] += 1
    if addresses["ipv6"]:
        counters["ipv6_tcp_ok"] += 1
    if not tcp_probe(endpoint, timeout=2):
        counters["first_resolved_ip_tcp_failed"] += 1
        if addresses["ipv4"] or addresses["ipv6"]:
            counters["address_family_or_order_mismatch"] += 1
        return counters
    counters["checker_tcp_ok"] += 1

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = {
        "log": {"level": "error"},
        "inbounds": [{
            "type": "mixed", "tag": "local",
            "listen": "127.0.0.1", "listen_port": port,
        }],
        "outbounds": [outbound],
        "route": {"final": "proxy"},
    }

    with tempfile.TemporaryDirectory(prefix="mamin-safe-probe-") as workdir:
        cfg = Path(workdir) / "config.json"
        cfg.write_text(json.dumps(config), encoding="utf-8")
        os.chmod(cfg, 0o600)
        # Captured stderr is NEVER printed because it might contain credentials.
        try:
            check = subprocess.run(
                [sing_box, "check", "-c", str(cfg)],
                capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            counters["sing_box_check_error"] += 1
            return counters
        if check.returncode != 0:
            counters["sing_box_config_rejected"] += 1
            return counters
        counters["sing_box_config_ok"] += 1

        # Temporarily capture errors in a root-private directory, then delete.
        # Never expose the raw log: it can include hostnames or credentials.
        log_path = Path(workdir) / "singbox-errors.log"
        try:
            with log_path.open("wb") as private_log:
                os.chmod(log_path, 0o600)
                process = subprocess.Popen(
                    [sing_box, "run", "-c", str(cfg)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=private_log, start_new_session=True)
        except OSError:
            counters["sing_box_start_error"] += 1
            return counters
        try:
            ready = False
            for _ in range(25):
                if process.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        ready = True
                        break
                except OSError:
                    time.sleep(0.1)
            if not ready:
                counters["local_proxy_not_ready"] += 1
                return counters
            counters["local_proxy_ready"] += 1

            exit_code, status = curl_probe(port, CONTROL_URL, timeout=10)
            counters[f"control_curl_exit_{exit_code}"] += 1
            if 200 <= status < 400:
                counters["control_https_ok"] += 1
            elif status == 0:
                counters["control_https_no_response"] += 1
            elif status == 403:
                counters["control_https_403"] += 1
            else:
                counters["control_https_other_status"] += 1

            if not (200 <= status < 400):
                return counters
            all_services = True
            for name, url in SERVICE_URLS.items():
                code, _ = http_probe(port, url, timeout=9)
                if 200 <= code < 400:
                    counters["service_" + name + "_ok"] += 1
                else:
                    all_services = False
                    counters["service_" + name + "_failed"] += 1
            if all_services:
                counters["strict_checker_would_pass"] += 1
        finally:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            for kind in classify_run_errors(log_path):
                counters[kind] += 1
    return counters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk-file", type=Path, required=True)
    ap.add_argument("--max-candidates", type=int, default=12)
    ap.add_argument("--sing-box", default="/opt/gwzhub/mamin-source/bin/sing-box")
    args = ap.parse_args()
    if not 1 <= args.max_candidates <= 20:
        ap.error("max-candidates must be 1..20")
    os.umask(0o077)
    from mamin_signing_key import pinned_bootstrap_key
    from mamin_verify_import import verify_rs256, b64url, fetch_catalog, vetted_nodes, KEY_ID
    from urllib.parse import parse_qs, urlsplit
    if not args.apk_file.is_file():
        raise SystemExit("Pinned APK missing; audit refused")
    key = pinned_bootstrap_key(args.apk_file)
    catalog = fetch_catalog()
    if (catalog.get("algorithm"), catalog.get("format"), catalog.get("key_id")) != (
            "RS256", "mamin-bootstrap-v2", KEY_ID):
        raise SystemExit("Unexpected signed catalogue metadata")
    verify_rs256(b64url(catalog["payload"]), b64url(catalog["signature"]), public_key_der=key)
    payload = json.loads(b64url(catalog["payload"]))
    if (payload.get("kind"), payload.get("package"), payload.get("schema")) != (
            "mamin-bootstrap-v2", "app.mamin.vpn", 1):
        raise SystemExit("Unexpected signed payload kind")
    now = int(time.time())
    if (type(payload.get("issued_at")) is not int or
        type(payload.get("expires_at")) is not int or
        payload["issued_at"] > now + 300 or payload["expires_at"] <= now):
        raise SystemExit("Signed catalogue expired/invalid")
    links = []
    for item in vetted_nodes(payload):
        if item.startswith("vless://") and parse_qs(urlsplit(item).query).get("security", [""])[0] == "reality":
            links.append(item)
    if not links:
        raise SystemExit("No signed VLESS Reality candidates")
    with tempfile.TemporaryDirectory(prefix="mamin-safe-candidates-") as td:
        source = Path(td) / "links.txt"
        source.write_text("\n".join(links) + "\n", encoding="utf-8")
        os.chmod(source, 0o600)
        links = unique_candidates(source, args.max_candidates)
    totals = Counter()
    for line in links:
        totals["checked"] += 1
        totals.update(inspect_one(line, args.sing_box))
    print(json.dumps({
        "signature_verified": True,
        "stage_counts_only": dict(sorted(totals.items())),
        "sample_count": len(links),
        "strict_rule": "control HTTPS + all four service HTTPS checks",
        "curl_exit_hint": "28=timeout; 35=TLS handshake; 56=read/reset; 60=certificate; 97=proxy handshake; 0=curl succeeded",
        "raw_sing_box_logs_emitted": False,
        "changed_private_feed": False,
        "changed_router": False,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
