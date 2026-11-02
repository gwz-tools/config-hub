#!/usr/bin/env python3
"""Read-only GWZHUB direct-outbound DNS vs proxy A/B.

No VLESS credentials, no live changes, only local loopback sing-box
and a 204 HTTPS check; prints categories/numbers only.
"""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from contextlib import suppress

BIN = "/opt/gwzhub/mamin-source/bin/sing-box-1.14.2"
URL = "https://www.gstatic.com/generate_204"

def probe(method, port=None):
    cmd = ["curl", "--silent", "--show-error", "-4", "--connect-timeout", "3",
           "--max-time", "11", "--output", os.devnull, "--write-out", "%{http_code}"]
    if method == "direct":
        cmd.extend(["--noproxy", "*"])
    elif method == "http_connect":
        cmd.extend(["--noproxy", "", "--proxy", f"http://127.0.0.1:{port}"])
    elif method == "socks_client_ipv4_dns":
        cmd.extend(["--noproxy", "", "--socks5", f"127.0.0.1:{port}"])
    elif method == "socks_proxy_dns":
        cmd.extend(["--noproxy", "", "--socks5-hostname", f"127.0.0.1:{port}"])
    cmd.append(URL)
    try:
        x = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=14, check=False)
        code = int(x.stdout.strip()) if x.stdout.strip().isdigit() else 0
        return {"curl_exit": x.returncode, "http_status": code,
                "https_ok": x.returncode == 0 and 200 <= code < 400}
    except (OSError, subprocess.TimeoutExpired):
        return {"curl_exit": 124, "http_status": 0, "https_ok": False}

def bind_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def main():
    if os.geteuid() != 0:
        raise SystemExit("Use sudo, for protected temp files")
    if not Path(BIN).is_file():
        raise SystemExit("Isolated sing-box 1.14.2 binary missing")
    os.umask(0o077)
    results = {"direct_ipv4": probe("direct")}
    port = bind_port()
    cfg = {"log": {"level": "warn"},
           "inbounds": [{"type": "mixed", "listen": "127.0.0.1",
                         "listen_port": port, "tag": "local"}],
           "outbounds": [{"type": "direct", "tag": "direct"}],
           "route": {"final": "direct"}}
    with tempfile.TemporaryDirectory(prefix="gwzhub-direct-dns-") as d:
        config = Path(d) / "config.json"
        config.write_text(json.dumps(cfg), encoding="utf-8")
        os.chmod(config, 0o600)
        ck = subprocess.run([BIN, "check", "-c", str(config)],
                            capture_output=True, timeout=10)
        if ck.returncode:
            results["singbox_config"] = "rejected"
        else:
            results["singbox_config"] = "accepted"
            logfile = Path(d) / "private.log"
            with logfile.open("wb") as f:
                os.chmod(logfile, 0o600)
                process = subprocess.Popen([BIN, "run", "-c", str(config)],
                                           stdin=subprocess.DEVNULL,
                                           stdout=f, stderr=f,
                                           start_new_session=True)
            try:
                started = False
                for _ in range(30):
                    if process.poll() is not None:
                        break
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            started = True
                            break
                    except OSError:
                        time.sleep(0.1)
                results["singbox_loopback_ready"] = started
                if started:
                    for method in ("http_connect", "socks_client_ipv4_dns", "socks_proxy_dns"):
                        results[method] = probe(method, port)
            finally:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=2)
                if process.poll() is None:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    results["live_config_changed"] = False
    results["vless_credentials_accessed"] = False
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
