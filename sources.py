"""
Config Hub
Public data sources registry

This file contains only external source definitions.
No data processing is performed here.
"""


# ============================================================
# PRIMARY SOURCES
# ============================================================

PRIMARY_SOURCES = [

    {
        "name": "igareck_black_mobile_gitlab",
        "type": "gitlab",
        "priority": 100,
        "url":
        "https://gitlab.com/igareck/vpn-configs-for-russia/-/raw/main/BLACK_VLESS_RUS_mobile.txt"
    },

    {
        "name": "igareck_black_full_gitlab",
        "type": "gitlab",
        "priority": 95,
        "url":
        "https://gitlab.com/igareck/vpn-configs-for-russia/-/raw/main/BLACK_VLESS_RUS.txt"
    },


    {
        "name": "igareck_white_mobile_gitlab",
        "type": "gitlab",
        "priority": 100,
        "url":
        "https://gitlab.com/igareck/vpn-configs-for-russia/-/raw/main/Vless-Reality-White-Lists-Rus-Mobile.txt"
    },


    {
        "name": "igareck_white_full_gitlab",
        "type": "gitlab",
        "priority": 90,
        "url":
        "https://gitlab.com/igareck/vpn-configs-for-russia/-/raw/main/WHITE-CIDR-RU-all.txt"
    },

]


# ============================================================
# MIRRORS
# ============================================================

MIRROR_SOURCES = [

    {
        "name": "igareck_black_mobile_codeberg",
        "type": "mirror",
        "priority": 98,
        "url":
        "https://codeberg.org/igareck/vpn-configs-for-russia/raw/branch/main/BLACK_VLESS_RUS_mobile.txt"
    },


    {
        "name": "igareck_black_mobile_jsdelivr",
        "type": "cdn",
        "priority": 80,
        "url":
        "https://cdn.jsdelivr.net/gh/igareck/vpn-configs-for-russia@main/BLACK_VLESS_RUS_mobile.txt"
    },

]


# ============================================================
# OPTIONAL COMMUNITY SOURCES
# ============================================================

COMMUNITY_SOURCES = [

    {
        "name": "hidashimora_collection",
        "type": "community",
        "priority": 50,
        "url": ""
    },

]


# ============================================================
# ALL SOURCES
# ============================================================

ALL_SOURCES = (
    PRIMARY_SOURCES
    +
    MIRROR_SOURCES
    +
    COMMUNITY_SOURCES
)


def get_sources():

    """
    Return sources sorted by priority.
    """

    return sorted(
        ALL_SOURCES,
        key=lambda x: x.get("priority", 0),
        reverse=True
    )


if __name__ == "__main__":

    for source in get_sources():

        print(
            source["priority"],
            source["name"],
            source["url"]
        )
