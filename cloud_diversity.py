"""Entry / exit network diversity for verified GWZHUB VLESS candidates.

Only metadata obtained from live tunnel checks is eligible for publishing.
IP geolocation is best-effort external data, not cryptographic proof.
"""
import ipaddress
import json
import re
import subprocess
from urllib.request import Request, urlopen

GEO_API = "https://ipwho.is/"
BAD_COUNTRIES = frozenset({"RU", "ZZ"})


def public_ip(value):
    addr = ipaddress.ip_address(value)
    if not addr.is_global:
        raise ValueError("Endpoint is not globally routable")
    return addr


def normalize_geo(payload):
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("Geolocation unavailable")
    address = str(public_ip(payload.get("ip", "")))
    country = payload.get("country_code")
    conn = payload.get("connection")
    if not isinstance(country, str) or len(country) != 2 or not country.isalpha() or not isinstance(conn, dict):
        raise ValueError("Missing country or connection data")
    country = country.upper()
    if country in BAD_COUNTRIES:
        raise ValueError("Russian or unknown gateway is not eligible")
    number = conn.get("asn")
    if isinstance(number, str):
        number = number.removeprefix("AS").strip()
        number = int(number) if number.isdecimal() else 0
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ValueError("Missing network ASN")
    return {"ip": address, "country": country, "asn": number}


def entry_geo(ip):
    address = str(public_ip(ip))
    req = Request(GEO_API + address, headers={"User-Agent": "GWZHUB-diversity/1"})
    with urlopen(req, timeout=6) as response:
        if response.status != 200:
            raise ValueError("Geo API unavailable")
        result = json.loads(response.read(20000))
    data = normalize_geo(result)
    if data["ip"] != address:
        raise ValueError("Entry geo lookup returned another IP")
    return data


def exit_geo(port):
    """Lookup requester IP strictly *through* local sing-box proxy, never direct."""
    cmd = ["curl", "--silent", "--show-error", "--fail",
           "--noproxy", "", "--connect-timeout", "3", "--max-time", "7",
           "--proxy", f"http://127.0.0.1:{port}", GEO_API]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=9, check=False)
    if run.returncode != 0 or len(run.stdout) > 20000:
        raise ValueError("Geo lookup through tunnel failed")
    return normalize_geo(json.loads(run.stdout))


def enrich(entry_ip, proxy_port):
    # Exit is observed inside the tunnel; entry host is the actually resolved IP.
    # Both must be non-Russian, with a known network operator ASN.
    entry = entry_geo(entry_ip)
    exit_ = exit_geo(proxy_port)
    return {
        "entry_ip": entry["ip"], "entry_country": entry["country"],
        "entry_asn": entry["asn"],
        "exit_country": exit_["country"], "exit_asn": exit_["asn"],
        # Do not persist exact exit IP in published status.
    }


def network_key(ip):
    a = public_ip(ip)
    return str(ipaddress.ip_network(f"{a}/{24 if a.version == 4 else 48}", strict=False))


def eligible(row):
    try:
        return (row.get("entry_country") not in BAD_COUNTRIES
                and row.get("exit_country") not in BAD_COUNTRIES
                and all(isinstance(row.get(key), str) and re.fullmatch(r"[A-Z]{2}", row[key])
                        for key in ("entry_country", "exit_country"))
                and all(isinstance(row.get(key), int) and not isinstance(row[key], bool) and row[key] > 0
                        for key in ("entry_asn", "exit_asn"))
                and bool(network_key(row["entry_ip"])))
    except (ValueError, KeyError, TypeError):
        return False


def select(rows, limit):
    """Preserve ranking; hard one per entry /24 (/48 v6), max two per ASN.

    First pass prefers different entry and exit ASNs. Second pass permits a
    second node per ASN when results are sparse. No same-prefix duplication.
    Countries limited to 3 egress locations each.
    """
    picked = []
    prefixes, entry_asns, exit_asns, exits = set(), {}, {}, {}
    for allowed_asn_reuse in (1, 2):
        for item in rows:
            if len(picked) >= limit:
                break
            if item in picked or not eligible(item):
                continue
            prefix = network_key(item["entry_ip"])
            a, b, country = item["entry_asn"], item["exit_asn"], item["exit_country"]
            if (prefix in prefixes or entry_asns.get(a, 0) >= allowed_asn_reuse
                    or exit_asns.get(b, 0) >= allowed_asn_reuse
                    or exits.get(country, 0) >= 3):
                continue
            picked.append(item)
            prefixes.add(prefix)
            entry_asns[a] = entry_asns.get(a, 0) + 1
            exit_asns[b] = exit_asns.get(b, 0) + 1
            exits[country] = exits.get(country, 0) + 1
    summary = {
        "eligible": sum(eligible(x) for x in rows),
        "selected": len(picked),
        "unique_entry_prefixes": len(prefixes),
        "unique_entry_asns": len(entry_asns),
        "unique_exit_asns": len(exit_asns),
        "exit_countries": dict(sorted(exits.items())),
        "policy": "unique_entry_/24_or_/48_max_2_per_ASN_max_3_per_exit_country",
    }
    return picked, summary
