"""
GWZ Config Hub

Collector v1.6.9

Downloads VLESS sources,
normalizes remarks for ALL sources,
preserves original source information,
detects country and flag,
removes duplicates,
creates raw pool.

Unified remark format:

🇩🇪 | GWZ | Germany ...
🇫🇮 | GWZ | Finland ...
🌐 | GWZ | Unknown ...
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
# COUNTRY DATABASE
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
# COUNTRY ALIASES
# ============================================================


COUNTRY_ALIASES = {

    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "u.s.a": "US",
    "america": "US",

    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    "england": "GB",
    "uk": "GB",

    "south korea": "KR",
    "korea": "KR",

    "czechia": "CZ",
    "czech republic": "CZ",

    "russian federation": "RU",
    "russia": "RU",

    "uae": "AE",
    "united arab emirates": "AE",

    "hong kong": "HK",

    "taiwan": "TW",

    "moldova": "MD",

    "north macedonia": "MK",

    "bosnia": "BA",
    "bosnia and herzegovina": "BA"
}


# Add official country names automatically

for _code, _name in COUNTRY_NAMES.items():

    COUNTRY_ALIASES.setdefault(
        _name.lower(),
        _code
    )


# Longest names first

COUNTRY_ALIAS_ITEMS = sorted(

    COUNTRY_ALIASES.items(),

    key=lambda item:
    len(item[0]),

    reverse=True

)


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
            "GWZ-Collector/1.6.9",

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
# FLAG HELPERS
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


def flag_to_country_code(text):

    """
    Detect first flag emoji.

    Example:
    🇩🇪 -> DE
    🇫🇮 -> FI
    """


    match = re.search(

        r"([\U0001F1E6-\U0001F1FF])"
        r"([\U0001F1E6-\U0001F1FF])",

        text

    )


    if not match:

        return None


    letters = []


    for char in match.group(0):

        letters.append(

            chr(
                ord(char)
                - 127397
            )

        )


    code = "".join(
        letters
    ).upper()


    if code in COUNTRY_NAMES:

        return code


    return None


# ============================================================
# COUNTRY DETECTION
# ============================================================


def detect_country_code(remark):

    """
    Country detection priority:

    1. flag emoji
    2. OpenProxyList country code
    3. country name
    4. leading ISO country code
    """


    if not remark:

        return None


    decoded = unquote(
        remark
    ).strip()


    # --------------------------------------------------------
    # FLAG
    # --------------------------------------------------------


    code = flag_to_country_code(
        decoded
    )


    if code:

        return code


    # --------------------------------------------------------
    # OPENPROXYLIST FORMAT
    #
    # [openproxylist.com] DE 123456
    # --------------------------------------------------------


    match = re.search(

        r"\[openproxylist\.com\]"
        r"\s*"
        r"([A-Za-z]{2})\b",

        decoded,

        re.IGNORECASE

    )


    if match:

        code = (
            match.group(1)
            .upper()
        )


        if code in COUNTRY_NAMES:

            return code


    # --------------------------------------------------------
    # COUNTRY NAME / ALIAS
    # --------------------------------------------------------


    lowered = decoded.lower()


    for alias, alias_code in COUNTRY_ALIAS_ITEMS:

        pattern = (

            r"(?<![A-Za-z])"
            + re.escape(alias)
            + r"(?![A-Za-z])"

        )


        if re.search(
            pattern,
            lowered,
            re.IGNORECASE
        ):

            return alias_code


    # --------------------------------------------------------
    # LEADING ISO CODE
    #
    # DE server
    # FI Helsinki
    # NL proxy
    # --------------------------------------------------------


    match = re.match(

        r"^[\s\|\-_:]*"
        r"([A-Za-z]{2})"
        r"(?=[\s\|\-_:])",

        decoded

    )


    if match:

        code = (
            match.group(1)
            .upper()
        )


        if code in COUNTRY_NAMES:

            return code


    return None


# ============================================================
# CLEAN GENERIC REMARK
# ============================================================


def clean_generic_remark(
    remark,
    country_code
):

    """
    Remove duplicated flag / country information
    from the beginning of an original remark.

    Original:
    🇩🇪 Germany Frankfurt

    Result:
    Frankfurt
    """


    if not remark:

        return ""


    result = unquote(
        remark
    ).strip()


    # --------------------------------------------------------
    # REMOVE EXISTING GWZ PREFIX
    #
    # Prevent:
    #
    # 🇩🇪 | GWZ | Germany
    # becoming
    # 🇩🇪 | GWZ | Germany 🇩🇪 | GWZ | Germany
    # --------------------------------------------------------


    result = re.sub(

        r"^[\U0001F1E6-\U0001F1FF]{2}"
        r"\s*\|\s*GWZ\s*\|\s*"
        r"[^|]+"
        r"\s*",

        "",

        result,

        flags=re.IGNORECASE

    )


    # --------------------------------------------------------
    # REMOVE LEADING FLAG
    # --------------------------------------------------------


    result = re.sub(

        r"^[\U0001F1E6-\U0001F1FF]{2}",

        "",

        result

    )


    result = result.strip(
        " |-_:"
    )


    if not country_code:

        return result


    country_name = COUNTRY_NAMES.get(
        country_code,
        ""
    )


    # --------------------------------------------------------
    # REMOVE COUNTRY NAME FROM BEGINNING
    # --------------------------------------------------------


    possible_names = [

        country_name,

        country_code

    ]


    for alias, alias_code in COUNTRY_ALIAS_ITEMS:

        if alias_code == country_code:

            possible_names.append(
                alias
            )


    possible_names = sorted(

        set(
            possible_names
        ),

        key=len,

        reverse=True

    )


    for value in possible_names:

        if not value:

            continue


        pattern = (

            r"^"
            + re.escape(value)
            + r"(?=$|[\s\|\-_:])"

        )


        new_result = re.sub(

            pattern,

            "",

            result,

            count=1,

            flags=re.IGNORECASE

        )


        if new_result != result:

            result = new_result.strip(
                " |-_:"
            )

            break


    return result


# ============================================================
# OPENPROXYLIST REMARK
# ============================================================


def format_openproxylist_remark(
    decoded,
    country_code
):

    """
    Input:

    [openproxylist.com] DE 16519301

    Output:

    🇩🇪 | GWZ | Germany [openproxylist.com] 16519301
    """


    suffix = ""


    match = re.match(

        r"^\[openproxylist\.com\]"
        r"\s*"
        r"([A-Za-z]{2})?"
        r"\s*"
        r"(.*)$",

        decoded,

        re.IGNORECASE

    )


    if match:

        suffix = (
            match.group(2)
            or ""
        ).strip()


    flag = country_flag(
        country_code
    )


    country_name = COUNTRY_NAMES.get(

        country_code,

        "Unknown"

    )


    result = (

        f"{flag} | GWZ | "
        f"{country_name} "
        f"[openproxylist.com]"

    )


    if suffix:

        result += (
            f" {suffix}"
        )


    return result


# ============================================================
# STANDARD GWZ REMARK
# ============================================================


def standardize_remark(
    link,
    source
):

    """
    Apply the same GWZ naming structure
    to EVERY published VLESS configuration.

    Format:

    FLAG | GWZ | COUNTRY original-details
    """


    if "#" in link:

        base, fragment = link.split(
            "#",
            1
        )

        decoded = unquote(
            fragment
        ).strip()

    else:

        base = link

        decoded = ""


    country_code = detect_country_code(
        decoded
    )


    # --------------------------------------------------------
    # SPECIAL CASE:
    # OPENPROXYLIST
    # --------------------------------------------------------


    if (
        source.get("type")
        == "openproxylist"
        or "[openproxylist.com]"
        in decoded.lower()
    ):

        if not country_code:

            country_code = "XX"


        if country_code in COUNTRY_NAMES:

            new_remark = format_openproxylist_remark(

                decoded,

                country_code

            )

        else:

            suffix = re.sub(

                r"^\[openproxylist\.com\]\s*",

                "",

                decoded,

                flags=re.IGNORECASE

            ).strip()


            new_remark = (

                "🌐 | GWZ | Unknown "
                "[openproxylist.com]"

            )


            if suffix:

                new_remark += (
                    f" {suffix}"
                )


    # --------------------------------------------------------
    # ALL OTHER SOURCES
    # --------------------------------------------------------


    else:

        if country_code:

            flag = country_flag(
                country_code
            )


            country_name = COUNTRY_NAMES.get(

                country_code,

                country_code

            )


            suffix = clean_generic_remark(

                decoded,

                country_code

            )


            new_remark = (

                f"{flag} | GWZ | "
                f"{country_name}"

            )


            if suffix:

                new_remark += (
                    f" {suffix}"
                )


        else:

            suffix = clean_generic_remark(

                decoded,

                None

            )


            new_remark = (
                "🌐 | GWZ | Unknown"
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


    if not link.startswith(
        "vless://"
    ):

        return ""


    return standardize_remark(

        link,

        source

    )


# ============================================================
# CONNECTION IDENTITY
# ============================================================


def connection_identity(link):

    """
    Ignore display name after # while comparing
    duplicate VLESS configurations.
    """

    return link.split(
        "#",
        1
    )[0]


# ============================================================
# DEDUPLICATION
# ============================================================


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


            normalized_links = []


            for item in links:

                normalized = normalize_link(

                    item,

                    source

                )


                if normalized:

                    normalized_links.append(
                        normalized
                    )


            links = normalized_links


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
    # SAVE RAW POOL
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


    # ========================================================
    # SUMMARY
    # ========================================================


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
