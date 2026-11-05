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
    # 0XRADIKAL TOP 100
    # Upstream pre-ranked pool; collector extracts VLESS only.
    # Highest discovery priority for GWZHUB candidates.
    # ========================================================

    {
        "name": "0xradikal_top100",

        "url":
        "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/top100.txt",

        "type": "github",

        "priority": 110,

        "enabled": True,

        "remark_mode": "keep",

        "tags": [
            "vless",
            "top100",
            "pretested",
            "priority"
        ]
    },

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
    # ADDITIONAL GWZHUB DISCOVERY SOURCES
    # ========================================================

    {
        "name": "epodonios_vless",
        "url": "https://raw.githubusercontent.com/Epodonios/v2ray-configs/refs/heads/main/Splitted-By-Protocol/vless.txt",
        "type": "github",
        "priority": 85,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "matinghanbari_vless",
        "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/vless.txt",
        "type": "github",
        "priority": 84,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "0xradikal_verified",
        "url": "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/verified/configs.txt",
        "type": "github",
        "priority": 83,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "aviamasters_verified",
        "url": "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/main/verified_configs.txt",
        "type": "github",
        "priority": 82,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "morpheus_best",
        "url": "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/subs/bundles/best.txt",
        "type": "github",
        "priority": 79,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "morpheus_reality",
        "url": "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/subs/bundles/reality.txt",
        "type": "github",
        "priority": 78,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "au1rxx",
        "url": "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/v2ray-base64.txt",
        "type": "github",
        "priority": 77,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    {
        "name": "alirewa_main",
        "url": "https://raw.githubusercontent.com/Alirewa/V2ray-Configs/main/config.txt",
        "type": "github",
        "priority": 76,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless", "additional", "discovery"]
    },

    # ========================================================
    # VERIFIED PUBLIC FEEDS: SOURCE AUDIT 2026-11-05
    # These respond with VLESS. Reachability of nodes is checked downstream.
    # Avoid mirroring the same upstream across GitHub/GitLab/Codeberg.
    # ========================================================

    {
        "name": "sakha_openray",
        "url": "https://raw.githubusercontent.com/sakha1370/OpenRay/main/output/all_valid_proxies.txt",
        "type": "github",
        "priority": 88,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","mamin_discovery"]
    },

    {
        "name": "cyberportal_cp005",
        "url": "https://gitverse.ru/cyberportal/wl/content/master/CP-005.txt",
        "type": "gitverse",
        "priority": 86,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","cyberportal","mobile"]
    },

    {
        "name": "cyberportal_cp038",
        "url": "https://gitverse.ru/cyberportal/wl/content/master/CP-038.txt",
        "type": "gitverse",
        "priority": 85,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","cyberportal","lite"]
    },

    {
        "name": "cyberportal_cp041",
        "url": "https://gitverse.ru/cyberportal/wl/content/master/CP-041.txt",
        "type": "gitverse",
        "priority": 83,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","cyberportal","mix"]
    },

    {
        "name": "cyberportal_cp002",
        "url": "https://gitverse.ru/cyberportal/wl/content/master/CP-002.txt",
        "type": "gitverse",
        "priority": 75,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","cyberportal","black"]
    },

    {
        "name": "cyberportal_cp003",
        "url": "https://gitverse.ru/cyberportal/wl/content/master/CP-003.txt",
        "type": "gitverse",
        "priority": 74,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","cyberportal","mobile"]
    },

    {
        "name": "mehrtat_vless",
        "url": "https://raw.githubusercontent.com/mehrtat/vless-collector/main/vless.txt",
        "type": "github",
        "priority": 73,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","mamin_discovery"]
    },

    {
        "name": "roosterkid_v2ray",
        "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt",
        "type": "github",
        "priority": 72,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","mamin_discovery"]
    },

    {
        "name": "igareck_white_mobile",
        "url": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
        "type": "github",
        "priority": 71,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","igareck","mobile"]
    },

    {
        "name": "igareck_white_cidr",
        "url": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
        "type": "github",
        "priority": 70,
        "enabled": True,
        "remark_mode": "keep",
        "tags": ["vless","igareck","white_list"]
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
