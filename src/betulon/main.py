import datetime
import json
import logging
import os
import pathlib
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from mastodon import Mastodon
from markdownify import markdownify as md

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Bookmark:
    url: str
    title: str
    description: str
    creation_time: datetime.datetime
    tags: List[str]


def get_json_state(filename: str) -> Optional[Dict]:
    """
    Read a json file containg the state.
    If empty, non-existing, or malformed returns `None`
    """

    path = os.getenv("STATE_PATH", ".") / pathlib.Path(filename)
    try:
        with open(path, "r") as f:
            content = f.read()
        logger.debug(f"File {path} read")
    except FileNotFoundError:
        logger.info(f"{filename} not found, returning None")
        return None

    try:
        state = json.loads(content)
        logger.info(f"state loaded, excerpt {str(state)[:100]}")
        return state
    except json.JSONDecodeError:
        path.unlink()  # it is malformed
        logger.warning(f"{filename} malformed, removing")
        return None


def write_json_state(state: Dict, filename: str) -> None:
    path = os.getenv("STATE_PATH", ".") / pathlib.Path(filename)
    with open(path, "w") as f:
        f.write(json.dumps(state))
        logger.debug(f"state dumped to {path}")


def get_new_min_id(masto: Mastodon) -> int:
    bookmarks = masto.bookmarks()
    # when calling `.bookmarks()`, we get by default the last bookmarks
    # and the _pagination_prev["min_id"] contains the `min_id` of the most recent bookmark
    min_id = bookmarks._pagination_prev["min_id"]
    logger.info(f"The new min_id for next time is {min_id}")
    return min_id


def get_bookmarks(masto: Mastodon, min_id=None) -> List[Bookmark]:
    first_page = masto.bookmarks()

    if not min_id:
        bookmarks = masto.fetch_remaining(first_page)  # see docs fetch_remaining
    else:
        # if we have `min_id`, we can discard `first_page`, except for getting `new_min_id`
        logger.debug(f"Calling masto.bookmarks with min_id={min_id}")
        page = masto.bookmarks(min_id=min_id)
        bookmarks = page
        logger.info(f"loaded {len(page)} bookmarks")
        while page:
            page = masto.fetch_previous(page)  # fetch_previous fetches newer toots
            logger.info(f"loaded {len(page)} bookmarks")
            bookmarks.extend(page)

    logger.info(f"bookmarks contains {len(bookmarks)} bookmarks")
    return [
        Bookmark(
            url=bookmark["url"],
            title="toot by " + bookmark["account"]["url"],
            description=md(bookmark["content"]),
            creation_time=bookmark["created_at"],
            tags=[tag["name"] for tag in bookmark["tags"]],
        )
        for bookmark in bookmarks
    ]


def db_path() -> str:
    path = os.getenv("DB_PATH", "test.sqlite")
    logger.info(f"Database path set to {path}")
    return path


def add_connection(func):
    """Ensure we have a working sqlite3 con object"""

    def wrapper(*args, **kwargs):
        _path = kwargs.get("path", db_path())
        conn = kwargs.get("conn")
        if not conn:
            conn = sqlite3.connect(_path)
        kwargs["conn"] = conn
        result = func(*args, **kwargs)
        conn.close()
        return result

    return wrapper


@add_connection
def insert_bookmarks(
    bookmarks: List[Bookmark],
    extra_tags: Tuple[str] = ("mastodon_bookmark",),
    conn: Optional[sqlite3.Connection] = None,
    _path: Optional[str] = None,
) -> None:
    if not conn and _path:
        conn = sqlite3.connect(_path)
    bookmark_sql = """
    INSERT INTO
    Bookmarks(URL, Title, Description, Visibility, CreationTime) 
    VALUES(?, ?, ?, ?, ?)
    RETURNING ID
    """
    tag_sql = """
    INSERT INTO
    TagsToPosts(TagName,PostID)
    VALUES(?, ?)
    """
    cursor = conn.cursor()
    for bookmark in reversed(
        bookmarks
    ):  # we reverse because the API returned bookmarks in inverted order
        cursor.execute(
            bookmark_sql,
            (
                bookmark.url,
                bookmark.title,
                bookmark.description,
                1,  # bookmarks can be visible by default when coming from Mastodon
                bookmark.creation_time.replace(tzinfo=None).strftime("%F %T.%f")[
                    :-3
                ],  # betula doesn't want a timezone and wants milliseconds
            ),
        )
        row = cursor.fetchone()
        if row:
            (inserted_id,) = row
            tags = list(extra_tags)

            for tag in tags + bookmark.tags:
                cursor.execute(tag_sql, (tag, inserted_id))
    conn.commit()


def cli():
    # logging
    log_level = os.getenv("LOG_LEVEL", "DEBUG")
    logger.setLevel(log_level)
    path = pathlib.Path(os.getenv("LOG_PATH", "."))
    filepath = path / pathlib.Path(f"{__name__}.log")
    handler = logging.FileHandler(filepath, mode="a", encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    logger.addHandler(handler)

    masto = Mastodon(
        access_token=os.getenv("MASTODON_ACCESS_TOKEN"),
        api_base_url=os.getenv("MASTODON_URL"),
    )
    min_id_dct = get_json_state("min_id.json")
    if min_id_dct:
        min_id = min_id_dct.get("min_id")
    else:
        min_id = None

    succeeded = False
    while not succeeded:
        new_min_id = get_new_min_id(masto)
        bookmarks = get_bookmarks(masto, min_id)
        if new_min_id == get_new_min_id(
            masto
        ):  # this happens if the user didn't add any new bookmark while processing
            insert_bookmarks(bookmarks)
            write_json_state({"min_id": new_min_id}, "min_id.json")
            succeeded = True
        else:
            logger.warning("The user added new bookmarks. Skipping writing to db")


if __name__ == "__main__":
    cli()
