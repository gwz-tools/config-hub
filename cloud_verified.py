#!/usr/bin/env python3
"""Independent cloud VLESS checker.

A GitHub runner checks HTTPS THROUGH each VLESS tunnel (not direct from runner).
Checks are indicative of the runner's network, not the subscriber's ISP.
Never replace a usable published subscription with an empty result.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

SERVICE_URLS = {
    "gemini": "https://gemini.google.com/",
    "instagram": "https://www.instagram.com/",
    "meta": "https://www.facebook.com/",
    "youtube": "https://www.youtube.com/",
}
CONTROL_URL = "https://www.gstatic.com/generate_204"
SUPPORTED_TRANSPORTS = {"tcp", "ws", "grpc"}


def param(query, key, default=""):
    return query.get(key, [default])[0]


def parse_vless(link):
    """Parse only known-safe VLESS forms; leave the original line unchanged for clients."""
    link = link.strip()
    parsed = urlsplit(link)
    if parsed.scheme != "vless" or not parsed.hostname or not parsed.port:
        raise ValueError("Invalid VLESS endpoint")
    UUID(parsed.username or "")
    if not (1 <= parsed.port <= 65535):
        raise ValueError("Port outside range")
    # Do not let untrusted public lists cause probes of local or reserved hosts.
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            raise ValueError("Non-public endpoint")
    except ValueError as exc:
        if str(exc) == "Non-public endpoint":
            raise
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
            raise ValueError("Local endpoint") from exc
    q = parse_qs(parsed.query, keep_blank_values=True)
    security = param(q, "security", "none")
    transport = param(q, "type", "tcp")
    if security not in {"reality", "tls"} or transport not in SUPPORTED_TRANSPORTS:
        raise ValueError("Unsupported security or transport")
    if param(q, "allowInsecure", "0") in {"1", "true"}:
        raise ValueError("Insecure TLS")
    outbound = {
        "type": "vless",
        "tag": "proxy",
        "server": parsed.hostname,
        "server_port": parsed.port,
        "uuid": parsed.username,
    }
    flow = param(q, "flow")
    if flow:
        if flow != "xtls-rprx-vision" or transport != "tcp":
            raise ValueError("Unsupported flow")
        outbound["flow"] = flow

    tls = {
        "enabled": True,
        "server_name": param(q, "sni", parsed.hostname),
        "insecure": False,
    }
    if param(q, "fp"):
        tls["utls"] = {"enabled": True, "fingerprint": param(q, "fp")}
    if param(q, "alpn"):
        tls["alpn"] = param(q, "alpn").split(",")
    if security == "reality":
        if not param(q, "pbk"):
            raise ValueError("Reality missing public key")
        tls["reality"] = {
            "enabled": True,
            "public_key": param(q, "pbk"),
            "short_id": param(q, "sid"),
        }
    outbound["tls"] = tls
    if transport == "ws":
        outbound["transport"] = {
            "type": "ws",
            "path": param(q, "path", "/"),
        }
        if param(q, "host"):
            outbound["transport"]["headers"] = {"Host": param(q, "host")}
    elif transport == "grpc":
        outbound["transport"] = {
            "type": "grpc",
            "service_name": param(q, "serviceName"),
        }
    return outbound


def public_endpoint(hostname, port):
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        valid = [x[4] for x in addresses if ipaddress.ip_address(x[4][0]).is_global]
        return valid[0] if valid else None
    except (OSError, ValueError):
        return None


def tcp_probe(endpoint, timeout=2):
    try:
        with socket.create_connection(endpoint, timeout=timeout):
            return True
    except OSError:
        return False


def http_probe(port, url, timeout=7):
    """Return (HTTP status, elapsed). A 403 is transport reachability, NOT site access."""
    command = [
        "curl", "--silent", "--show-error", "--noproxy", "",
        "--connect-timeout", "3", "--max-time", str(timeout),
        "--output", os.devnull, "--write-out", "%{http_code}",
        "--proxy", f"http://127.0.0.1:{port}", url,
    ]
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2)
        code = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        return (code if result.returncode == 0 else 0, round(time.monotonic() - started, 3))
    except (subprocess.TimeoutExpired, OSError):
        return 0, round(time.monotonic() - started, 3)


def test_candidate(link, sing_box):
    try:
        outbound = parse_vless(link)
        endpoint = public_endpoint(outbound["server"], outbound["server_port"])
        if not endpoint or not tcp_probe(endpoint):
            return None
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        config = {
            "log": {"level": "error"},
            "inbounds": [{"type": "mixed", "tag": "local", "listen": "127.0.0.1", "listen_port": port}],
            "outbounds": [outbound],
            "route": {"final": "proxy"},
        }
        with tempfile.TemporaryDirectory(prefix="gwz-cloud-") as workdir:
            cfg = Path(workdir) / "config.json"
            cfg.write_text(json.dumps(config), encoding="utf-8")
            proc = subprocess.Popen(
                [sing_box, "run", "-c", str(cfg)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                ready = False
                for _ in range(25):
                    if proc.poll() is not None:
                        break
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            ready = True
                            break
                    except OSError:
                        time.sleep(0.1)
                if not ready:
                    return None
                control_code, latency = http_probe(port, CONTROL_URL)
                if not (200 <= control_code < 400):
                    return None
                statuses = {}
                for name, url in SERVICE_URLS.items():
                    code, _ = http_probe(port, url)
                    statuses[name] = code
                functional = sum(200 <= code < 400 for code in statuses.values())
                if functional < len(SERVICE_URLS):
                    return None
                return {"line": link, "functional": functional, "latency": latency,
                        "statuses": statuses}
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def unique_candidates(source, limit):
    if not source.exists():
        raise FileNotFoundError(f"Candidate list missing: {source}")
    seen = set()
    lines = []
    for line in source.read_text(encoding="utf-8").splitlines():
        link = line.strip()
        if not link.startswith("vless://"):
            continue
        try:
            p = urlsplit(link)
            q = parse_qs(p.query)
            # Same server, port, identity and protocol settings regardless of remarks.
            key = (p.hostname, p.port, p.username,
                   tuple(sorted((k, tuple(v)) for k, v in q.items())))
            parse_vless(link)
        except (ValueError, TypeError):
            continue
        if key not in seen:
            seen.add(key)
            lines.append(link)
        if len(lines) >= limit:
            break
    return lines


def build(args):
    candidates = unique_candidates(args.source, args.max_candidates)
    if not candidates:
        raise RuntimeError("No valid candidate URLs")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(test_candidate, x, args.sing_box) for x in candidates]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    results.sort(key=lambda x: (-x["functional"], x["latency"]))
    stats = Counter()
    for result in results:
        for name, status in result["statuses"].items():
            if 200 <= status < 400:
                stats[name] += 1
    metadata = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_note": "HTTP requests tested via VLESS from GitHub runner; not proof of access in Russia",
        "candidates_tested": len(candidates),
        "passed": len(results),
        "published": False,
        "services_with_http_2xx_3xx": {k: stats[k] for k in SERVICE_URLS},
    }
    # No zero updates. Preserve the last GOOD subscription rather than publish empty.
    if len(results) >= args.min_live:
        text = "".join(x["line"] + "\n" for x in results[:args.max_published])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                         prefix=".cloud-", delete=False) as tmp:
            tmp.write(text)
            temp_name = tmp.name
        os.replace(temp_name, args.output)
        metadata["published"] = True
        metadata["published_count"] = min(len(results), args.max_published)
    else:
        metadata["reason"] = f"Safety guard: {len(results)} < {args.min_live} validated nodes"
        if not args.output.exists() or not any(
                l.startswith("vless://") for l in args.output.read_text(encoding="utf-8").splitlines()):
            raise RuntimeError(metadata["reason"] + "; no previous good cloud subscription")
        metadata["stale_previous_list_retained"] = True
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/gwzhub_candidates.txt"))
    parser.add_argument("--output", type=Path, default=Path("cloud-vless.txt"))
    parser.add_argument("--metadata", type=Path, default=Path("data/cloud-status.json"))
    parser.add_argument("--sing-box", default="sing-box")
    parser.add_argument("--max-candidates", type=int, default=48)
    parser.add_argument("--max-published", type=int, default=40)
    parser.add_argument("--min-live", type=int, default=3)
    parser.add_argument("--workers", type=int, default=6)
    build(parser.parse_args())
