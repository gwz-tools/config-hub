"""
GWZ Config Hub

Sources registry

Central list of external configuration sources.
Each source contains metadata for:
- collector
- validation
- monitoring
- history tracking
"""


from datetime import datetime, timezone


# ============================================================
# SOURCE REGISTRY
# ============================================================


SOURCES = [

    # ========================================================
    # IGARECK GITHUB
    # Main trusted sources
    # ========================================================

    {
        "name": "igareck_mobile",

        "url":
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt",

        "type": "github",

        "priority": 100,

        "enabled": True,

        "remark_mode": "keep",

        "tags": [
            "vless",
            "mobile",
            "reality",
            "trusted"
        ]
    },


    {
        "name": "igareck_full",

        "url":
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt",

        "type": "github",

        "priority": 90,

        "enabled": True,

        "remark_mode": "keep",

        "tags": [
            "vless",
            "full",
            "reality",
            "backup"
        ]
    },


    # ========================================================
    # OPENPROXYLIST
    #
    # Original attribution is preserved.
    #
    # Example:
    #
    # 🇩🇪 | GWZ | Germany [openproxylist.com] 12345678
    #
    # Only VLESS entries are collected.
    # ========================================================

    {
        "name": "openproxylist_v2ray",

        "url":
        "https://openproxylist.com/v2ray/rawlist/text",

        "type": "openproxylist",

        "priority": 80,

        "enabled": True,

        "remark_mode": "gwz_openproxylist",

        "tags": [
            "vless",
            "external",
            "attributed"
        ]
    },


    # ========================================================
    # FUTURE MIRRORS
    # Disabled until verified
    # ========================================================

    {
        "name": "igareck_mobile_gitlab",

        "url":
        "https://gitlab.com/igareck/black_mobile/-/raw/main/config.txt",

        "type": "gitlab",

        "priority": 50,

        "enabled": False,

        "remark_mode": "keep",

        "tags": [
            "mirror",
            "legacy"
        ]
    },


    {
        "name": "igareck_white_mobile_gitlab",

        "url":
        "https://gitlab.com/igareck/white_mobile/-/raw/main/config.txt",

        "type": "gitlab",

        "priority": 40,

        "enabled": False,

        "remark_mode": "keep",

        "tags": [
            "white",
            "mirror"
        ]
    },

]


# ============================================================
# HELPERS
# ============================================================


def get_sources():
    """
    Return enabled sources sorted by priority.
    Highest priority first.
    """

    return sorted(

        [
            source
            for source in SOURCES
            if source.get(
                "enabled",
                False
            )
        ],

        key=lambda x:
        x.get(
            "priority",
            0
        ),

        reverse=True
    )


def get_source_names():
    """
    Return enabled source names.
    """

    return [

        source["name"]

        for source in get_sources()

    ]


def get_source_by_name(name):
    """
    Find source metadata by name.
    """

    for source in SOURCES:

        if source["name"] == name:

            return source

    return None


def get_metadata():
    """
    Return registry metadata.
    """

    return {

        "updated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "sources":
        len(SOURCES),

        "enabled":
        len(get_sources()),

        "enabled_names":
        get_source_names()

    }
