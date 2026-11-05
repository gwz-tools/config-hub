"""Offline policy gates for a possible authenticated Telegram-only WS/TCP fallback.

NOT a relay, not a VPN protocol, not an MTProxy. No actual TCP sockets.
"""
import ipaddress
import json
from pathlib import Path


class PolicyDenied(ValueError):
    pass


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise PolicyDenied("wrong policy version")
    ports = policy.get("allowed_ports")
    if not isinstance(ports, list) or not ports or any(
            type(x) is not int or x < 1 or x > 65535 for x in ports):
        raise PolicyDenied("invalid port allowlist")
    for key in ("max_queue_bytes", "max_frame_bytes", "max_open_sockets_per_session",
                "connect_timeout_ms", "idle_timeout_ms"):
        n = policy.get(key)
        if type(n) is not int or n <= 0:
            raise PolicyDenied("invalid resource cap")
    if not 1024 <= policy["max_frame_bytes"] <= policy["max_queue_bytes"] <= 1048576:
        raise PolicyDenied("unbounded frame or queue")
    if policy["max_open_sockets_per_session"] > 2:
        raise PolicyDenied("too many sockets")
    if not 1000 <= policy["connect_timeout_ms"] <= 15000:
        raise PolicyDenied("connect timeout outside policy")
    if not 10000 <= policy["idle_timeout_ms"] <= 300000:
        raise PolicyDenied("idle timeout outside policy")
    for key in ("require_authenticated_client", "require_server_side_rate_limit",
                "reject_hostnames"):
        if policy.get(key) is not True:
            raise PolicyDenied("required safety guard disabled")
    if policy.get("enabled") and (not policy.get("production_ready")
                                  or not policy.get("telegram_native_proxy_compatible")):
        raise PolicyDenied("fallback not ready")
    approved = []
    for raw in policy.get("allowed_destinations", []):
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise PolicyDenied("destination must be literal IP") from exc
        if not addr.is_global or (isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped):
            raise PolicyDenied("non-public or mapped destination")
        # No trust in synthetic IPv6 with embedded IPv4 until NAT64 mapping is verified.
        if isinstance(addr, ipaddress.IPv6Address) and (
                addr in ipaddress.ip_network("64:ff9b::/96") or
                addr in ipaddress.ip_network("64:ff9b:1::/48")):
            raise PolicyDenied("NAT64 requires verified mapping")
        approved.append(str(addr))
    if len(approved) != len(set(approved)) or len(approved) > 128:
        raise PolicyDenied("duplicate/unbounded allowlist")
    return set(approved)


def authorize_destination(host, port, policy):
    approved = validate_policy(policy)
    if type(port) is not int or port not in policy["allowed_ports"]:
        raise PolicyDenied("port not allowed")
    try:
        destination = ipaddress.ip_address(host)
    except ValueError as exc:
        raise PolicyDenied("hostnames rejected to avoid DNS rebinding") from exc
    if str(destination) not in approved:
        raise PolicyDenied("destination not explicitly approved")
    return str(destination), port


class BoundedQueue:
    """Resource accounting for an adapter; queue holds bytes, never grow unbounded."""
    def __init__(self, max_bytes, max_frame_bytes):
        if not 1 <= max_frame_bytes <= max_bytes <= 1048576:
            raise ValueError("invalid limits")
        self.max_bytes = max_bytes
        self.max_frame_bytes = max_frame_bytes
        self.pending = 0
        self.connected = False

    def ready(self):
        self.connected = True

    def enqueue(self, size):
        if not self.connected:
            raise PolicyDenied("TCP socket not connected")
        if type(size) is not int or size < 0 or size > self.max_frame_bytes:
            raise PolicyDenied("frame exceeds budget")
        if self.pending + size > self.max_bytes:
            raise PolicyDenied("backpressure: queue full")
        self.pending += size

    def acknowledge(self, size):
        if type(size) is not int or not 0 <= size <= self.pending:
            raise PolicyDenied("invalid acknowledgement")
        self.pending -= size

    def close(self):
        self.connected = False
        self.pending = 0


def load(path="experiments/telegram-fallback/policy.json"):
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_policy(p)
    return p
