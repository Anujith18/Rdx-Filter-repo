"""Central, user-facing RDX branding.

Internal package, class, database, and legacy environment names intentionally
remain unchanged so existing deployments and indexed data keep working.
"""

from os import environ


BRAND_NAME = environ.get("BRAND_NAME", "RDX AUTO FILTER")
BRAND_SHORT_NAME = environ.get("BRAND_SHORT_NAME", "RDX")
BRAND_TAGLINE = environ.get(
    "BRAND_TAGLINE",
    "SEARCH • STREAM • DOWNLOAD",
)

UPDATE_CHANNEL_LINK = environ.get(
    "CHNL_LNK",
    "https://t.me/rdxmovie_hd",
)
MOVIE_GROUP_LINK = environ.get(
    "GRP_LNK",
    "https://t.me/movie_search_group1",
)
OWNER_LINK = environ.get(
    "OWNER_LNK",
    "https://t.me/Extra_Ordinary_boy",
)
MOVIE_UPDATE_LINK = environ.get(
    "DEENDAYAL_MOVIE_UPDATE_CHANNEL_LNK",
    "https://t.me/+JYcBHgSBaNYxYjdl",
)

# Preserve upstream attribution unless the deployer supplies their own repo.
SOURCE_CODE_LINK = environ.get(
    "SOURCE_CODE_LINK",
    "https://github.com/RDX-EXPART/Rdx-auto-filter",
)

PROFILE_LOGO = environ.get(
    "PROFILE_LOGO",
    "https://graph.org/file/6f4d0195bf4934cfa6477-b639386b2d359a8e5f.jpg",
)
WELCOME_BANNER = environ.get(
    "WELCOME_BANNER",
    "https://graph.org/file/2aeb5faf6f952dd8c3ab9-e100691cd672eaa918.jpg",
)
NO_RESULTS_BANNER = environ.get(
    "NO_RESULTS_BANNER",
    "https://graph.org/file/7d1666e996bdf054b8d29-ad25c28d7b085ab429.jpg",
)
JOIN_CHANNEL_BANNER = environ.get(
    "JOIN_CHANNEL_BANNER",
    "https://graph.org/file/0947efb379e88cbdcb11b-601bff87761ad25551.jpg",
)
PREMIUM_BANNER = environ.get(
    "PREMIUM_BANNER",
    "https://graph.org/file/b33697ac8914376274321-d0d3db963f75b4af48.jpg",
)
