"""
Config Hub
Sources registry

Central list of external configuration sources.
"""


from datetime import datetime


SOURCES = [

    {
        "name": "igareck_black_mobile_gitlab",
        "url": "https://gitlab.com/igareck/black_mobile/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 10,
        "enabled": True
    },


    {
        "name": "igareck_white_mobile_gitlab",
        "url": "https://gitlab.com/igareck/white_mobile/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 9,
        "enabled": True
    },


    {
        "name": "igareck_black_full_gitlab",
        "url": "https://gitlab.com/igareck/black_full/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 8,
        "enabled": True
    },


    {
        "name": "igareck_white_full_gitlab",
        "url": "https://gitlab.com/igareck/white_full/-/raw/main/config.txt",
        "type": "gitlab",
        "priority": 7,
        "enabled": True
    },


    {
        "name": "github_backup",
        "url": "https://raw.githubusercontent.com/igareck/configs/main/config.txt",
        "type": "github",
        "priority": 5,
        "enabled": True
    }

]



def get_sources():

    return sorted(
        [
            x for x in SOURCES
            if x.get("enabled")
        ],
        key=lambda x: x["priority"],
        reverse=True
    )



def get_source_names():

    return [
        x["name"]
        for x in get_sources()
    ]



def get_metadata():

    return {

        "updated":
            datetime.utcnow().isoformat(),

        "sources":
            len(SOURCES),

        "enabled":
            len(get_sources())

    }
