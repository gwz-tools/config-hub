"""
GWZ Config Hub

Collector v1.6.8

Downloads sources,
extracts VLESS configs,
normalizes source remarks,
preserves source attribution,
removes duplicates,
creates raw pool.
"""


import os
import re
import html
import hashlib
import urllib.request


from datetime import datetime, timezone


from urllib.parse import (
    quote,
    unquote
)


from sources import get_sources
from source_status import update_source


# ============================================================
# PATHS
# ============================================================


RAW_FILE = "data/raw.txt"

LOG_FILE = "logs/collector.log"


os.makedirs(
    "data",
    exist_ok=True
)


os.makedirs(
    "logs",
    exist_ok=True
)


# ============================================================
# COUNTRY NAMES
# ============================================================


COUNTRY_NAMES = {

    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AL": "Albania",
    "AM": "Armenia",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "AZ": "Azerbaijan",

    "BA": "Bosnia and Herzegovina",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BO": "Bolivia",
    "BR": "Brazil",
    "BY": "Belarus",

    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CY": "Cyprus",
    "CZ": "Czech Republic",

    "DE": "Germany",
    "DK": "Denmark",
    "DO": "Dominican Republic",

    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "ES": "Spain",

    "FI": "Finland",
    "FR": "France",

    "GB": "United Kingdom",
    "GE": "Georgia",
    "GR": "Greece",

    "HK": "Hong Kong",
    "HR": "Croatia",
    "HU": "Hungary",

    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",

    "JP": "Japan",

    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KR": "South Korea",
    "KZ": "Kazakhstan",

    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",

    "MD": "Moldova",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "MN": "Mongolia",
    "MX": "Mexico",
    "MY": "Malaysia",

    "NG": "Nigeria",
    "NL": "Netherlands",
    "NO": "Norway",
    "NZ": "New Zealand",

    "PA": "Panama",
    "PE": "Peru",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PT": "Portugal",

    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",

    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",

    "TH": "Thailand",
    "TR": "Turkey",
    "TW": "Taiwan",

    "UA": "Ukraine",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",

    "VE": "Venezuela",
    "VN": "Vietnam",

    "ZA": "South Africa"
}


# ============================================================
# LOG
# ============================================================


def log(message):

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    line = (
        f"{timestamp} {message}"
    )


    print(
        line
    )


    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            line + "\n"
        )


# ============================================================
# DOWNLOAD
# ============================================================


def download(url):

    request = urllib.request.Request(

        url,

        headers={
            "User-Agent":
            "GWZ-Collector/1.6.8",

            "Accept":
            "text/plain,*/*",

            "Cache-Control":
            "no-cache"
        }

    )


    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:

        return response.read().decode(

            "utf-8",

            errors="ignore"

        )


# ============================================================
# EXTRACT VLESS
# ============================================================


def extract_vless(text):

    # Some external lists may contain HTML escaped
    # ampersands such as &amp;.
    #
    # Convert them back before extracting links.

    text = html.unescape(
        text
    )


    pattern = r"vless://[^\s<>\"']+"


    return re.findall(

        pattern,

        text,

        flags=re.MULTILINE

    )


# ============================================================
# FLAG
# ============================================================


def country_flag(country_code):

    code = (
        country_code
        .strip()
        .upper()
    )


    if (
        len(code) != 2
        or not code.isalpha()
    ):

        return "🌐"


    return "".join(

        chr(
            ord(char)
            + 127397
        )

        for char in code

    )


# ============================================================
# OPENPROXYLIST REMARK
# ============================================================


def format_openproxylist_remark(link):

    """
    Preserve OpenProxyList attribution
    and prepend GWZ branding.

    Input example:

    vless://...#%5Bopenproxylist.com%5D%20DE%201234567

    Output remark:

    🇩🇪 | GWZ | Germany [openproxylist.com] 1234567
    """


    if "#" not in link:

        return link


    base, fragment = link.split(
        "#",
        1
    )


    decoded = unquote(
        fragment
    ).strip()


    # Expected:
    #
    # [openproxylist.com] DE 1234567

    pattern = re.compile(

        r"^\[openproxylist\.com\]"
        r"\s*"
        r"([A-Za-z]{2})?"
        r"\s*"
        r"(.*)$",

        re.IGNORECASE

    )


    match = pattern.match(
        decoded
    )


    if not match:

        # We do not delete an unknown original remark.
        # GWZ is simply added before it.

        new_remark = (
            "🌐 | GWZ | "
            + decoded
        )


        encoded = quote(
            new_remark,
            safe=""
        )


        return (
            base
            + "#"
            + encoded
        )


    country_code = (
        match.group(1)
        or ""
    ).upper()


    suffix = (
        match.group(2)
        or ""
    ).strip()


    flag = country_flag(
        country_code
    )


    country_name = COUNTRY_NAMES.get(

        country_code,

        country_code

    )


    attribution = (
        "[openproxylist.com]"
    )


    if country_name:

        new_remark = (

            f"{flag} | GWZ | "
            f"{country_name} "
            f"{attribution}"

        )

    else:

        new_remark = (

            f"{flag} | GWZ | "
            f"{attribution}"

        )


    if suffix:

        new_remark += (
            f" {suffix}"
        )


    encoded = quote(

        new_remark,

        safe=""

    )


    return (
        base
        + "#"
        + encoded
    )


# ============================================================
# NORMALIZE
# ============================================================


def normalize_link(
    link,
    source
):

    link = (

        link
        .strip()
        .replace(
            "\r",
            ""
        )

    )


    remark_mode = source.get(

        "remark_mode",

        "keep"

    )


    if (
        remark_mode
        == "gwz_openproxylist"
    ):

        link = format_openproxylist_remark(
            link
        )


    return link


# ============================================================
# DEDUPLICATION
# ============================================================


def connection_identity(link):

    """
    Deduplicate by connection itself,
    ignoring the human-readable remark
    after #.

    This prevents the same server from
    surviving only because it has a
    different display name.
    """

    return link.split(
        "#",
        1
    )[0]


def remove_duplicates(items):

    result = []

    seen = set()


    for item in items:

        identity = connection_identity(
            item
        )


        key = hashlib.sha256(

            identity.encode(
                "utf-8"
            )

        ).hexdigest()


        if key in seen:

            continue


        seen.add(
            key
        )


        result.append(
            item
        )


    return result


# ============================================================
# HASH
# ============================================================


def checksum(text):

    return hashlib.sha256(

        text.encode(
            "utf-8"
        )

    ).hexdigest()


# ============================================================
# MAIN
# ============================================================


def main():

    sources = get_sources()


    log(
        f"Sources count: {len(sources)}"
    )


    all_links = []


    success = 0

    failed = 0


    for source in sources:

        name = source["name"]

        url = source["url"]


        try:

            log(
                f"Downloading {name}"
            )


            data = download(
                url
            )


            log(

                f"Downloaded {name} "
                f"chars={len(data)}"

            )


            links = extract_vless(
                data
            )


            links = [

                normalize_link(
                    item,
                    source
                )

                for item in links

            ]


            links = [

                item

                for item in links

                if item.startswith(
                    "vless://"
                )

            ]


            if links:

                all_links.extend(
                    links
                )


                success += 1


                update_source(
                    name,
                    True
                )


                log(

                    f"OK {name} "
                    f"links={len(links)}"

                )


            else:

                failed += 1


                update_source(
                    name,
                    False
                )


                log(
                    f"EMPTY {name}"
                )


        except Exception as e:

            failed += 1


            update_source(
                name,
                False
            )


            log(

                f"ERROR {name}: "
                f"{e}"

            )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    before = len(
        all_links
    )


    all_links = remove_duplicates(
        all_links
    )


    after = len(
        all_links
    )


    # ========================================================
    # SAVE
    # ========================================================

    output = "\n".join(
        all_links
    )


    with open(

        RAW_FILE,

        "w",

        encoding="utf-8"

    ) as f:

        f.write(
            output
        )


        if output:

            f.write(
                "\n"
            )


    log(

        "Collection finished "

        f"sources={len(sources)} "

        f"success={success} "

        f"failed={failed} "

        f"before={before} "

        f"after={after} "

        f"sha256={checksum(output)[:12]}"

    )


if __name__ == "__main__":

    main()
