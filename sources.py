"""
Config Hub
Sources registry

Central list of external configuration sources.
"""

from datetime import datetime


SOURCES = [

    # ========================================================
    # PRIMARY GWZ SOURCES
    # ========================================================

    {
        "name": "gwz_fast",
        "url": "https://raw.githubusercontent.com/alexandrovu96-stack/vpn-gwz/main/fast.txt",
        "type": "github",
        "priority": 100,
        "enabled": True,
        "tags": [
            "gwz",
            "primary"
        ]
    },


    {
        "name": "gwz_stable",
        "url": "https://raw.githubusercontent.com/alexandrovu96-stack/vpn-gwz/main/stable.txt",
        "type": "github",
        "priority": 90,
        "enabled": True,
        "tags": [
            "gwz",
            "stable"
        ]
    },


    # ========================================================
    # MIRRORS
    # ========================================================

    {
        "name": "gwz_gitlab_backup",
        "url": "https://gitlab.com/gwz-tools/vpn-gwz/-/raw/main/fast.txt",
        "type": "gitlab",
        "priority": 70,
        "enabled": True,
        "tags": [
            "mirror"
        ]
    },


    {
        "name": "gwz_codeberg_backup",
        "url": "https://codeberg.org/gwz-tools/vpn-gwz/raw/branch/main/fast.txt",
        "type": "codeberg",
        "priority": 60,
        "enabled": True,
        "tags": [
            "mirror"
        ]
    },


    # ========================================================
    # COMMUNITY SOURCES
    # ========================================================

    {
        "name": "igareck_black",
        "url": "https://gitlab.com/igareck/black_mobile/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 30,
        "enabled": True,
        "tags": [
            "community"
        ]
    },


]


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

    return [
        source["name"]
        for source in get_sources()
    ]



def get_metadata():

    return {
        "updated": datetime.utcnow().isoformat(),
        "sources": len(SOURCES),
        "enabled": len(get_sources())
    }
