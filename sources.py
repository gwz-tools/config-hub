"""
Config Hub
Sources registry

Central list of external configuration sources.
Each source contains metadata for collector,
validation and future monitoring.
"""

from datetime import datetime


# ============================================================
# SOURCE REGISTRY
# ============================================================

SOURCES = [

    {
        "name": "igareck_black_mobile_gitlab",
        "url": "https://gitlab.com/igareck/black_mobile/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 10,
        "enabled": True,
        "tags": [
            "mobile",
            "black"
        ]
    },


    {
        "name": "igareck_white_mobile_gitlab",
        "url": "https://gitlab.com/igareck/white_mobile/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 9,
        "enabled": True,
        "tags": [
            "mobile",
            "white"
        ]
    },


    {
        "name": "igareck_black_full_gitlab",
        "url": "https://gitlab.com/igareck/black_full/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 8,
        "enabled": True,
        "tags": [
            "full",
            "black"
        ]
    },


    {
        "name": "igareck_white_full_gitlab",
        "url": "https://gitlab.com/igareck/white_full/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 7,
        "enabled": True,
        "tags": [
            "full",
            "white"
        ]
    },


    {
        "name": "igareck_black_mobile_codeberg",
        "url": "https://codeberg.org/igareck/black_mobile/raw/branch/main/config.txt",
        "type": "codeberg",
        "priority": 6,
        "enabled": True,
        "tags": [
            "mobile",
            "mirror"
        ]
    },


    {
        "name": "igareck_white_full_gitlab_mirror",
        "url": "https://gitlab.com/igareck/white_full/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 5,
        "enabled": True,
        "tags": [
            "mirror"
        ]
    },


    {
        "name": "igareck_black_mobile_gitlab_jsdelivr",
        "url": "https://cdn.jsdelivr.net/gh/igareck/black_mobile/config.txt",
        "type": "jsdelivr",
        "priority": 4,
        "enabled": True,
        "tags": [
            "cdn",
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
    """

    return sorted(
        [
            source
            for source in SOURCES
            if source.get("enabled", False)
        ],
        key=lambda x: x.get("priority", 0),
        reverse=True
    )



def get_source_names():
    """
    Return source names list.
    """

    return [
        source["name"]
        for source in get_sources()
    ]



def get_metadata():
    """
    Return registry metadata.
    """

    return {
        "updated": datetime.utcnow().isoformat(),
        "sources": len(SOURCES),
        "enabled": len(get_sources())
    }
