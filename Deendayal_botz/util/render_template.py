#Thanks @dreamcinezone for helping in this journey 

import jinja2
from datetime import datetime
from pathlib import Path
from info import *
from branding import (
    BRAND_NAME,
    BRAND_TAGLINE,
    MOVIE_GROUP_LINK,
    OWNER_LINK,
    UPDATE_CHANNEL_LINK,
)
from Deendayal_botz.Bot import DeendayalBot
from Deendayal_botz.util.human_readable import humanbytes
from Deendayal_botz.util.file_properties import get_file_ids
from Deendayal_botz.server.exceptions import InvalidHash
import urllib.parse
import logging
import aiohttp


async def render_page(id, secure_hash, src=None):
    file = await DeendayalBot.get_messages(int(LOG_CHANNEL), int(id))
    file_data = await get_file_ids(DeendayalBot, int(LOG_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        logging.debug(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        logging.debug(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote_plus(file_data.file_name)}?hash={secure_hash}",
    )

    tag = file_data.mime_type.split("/")[0].strip()
    file_size = humanbytes(file_data.file_size)
    if tag in ["video", "audio"]:
        template_name = "req.html"
    else:
        template_name = "dl.html"
        async with aiohttp.ClientSession() as s:
            async with s.get(src) as u:
                file_size = humanbytes(int(u.headers.get("Content-Length")))

    template_dir = Path(__file__).resolve().parents[1] / "template"
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
    template = environment.get_template(template_name)

    file_name = file_data.file_name.replace("_", " ")

    return template.render(
        file_name=file_name,
        file_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
        brand_name=BRAND_NAME,
        brand_tagline=BRAND_TAGLINE,
        update_channel_link=UPDATE_CHANNEL_LINK,
        movie_group_link=MOVIE_GROUP_LINK,
        owner_link=OWNER_LINK,
        current_year=datetime.now().year,
    )
