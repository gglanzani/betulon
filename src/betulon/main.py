import datetime
import json
import logging
import os
import pathlib
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from mastodon import Mastodon

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

    path = pathlib.Path(filename)
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        logger.info(f"{filename} not found, returning None")
        return None

    try:
        state = json.loads(content)
        return state
    except json.JSONDecodeError:
        path.unlink()  # it is malformed
        logger.warning(f"{filename} malformed, removing")
        return None


def write_json_state(dct: Dict, filename: str) -> None:
    path = pathlib.Path(filename)
    with open(path, "w") as f:
        f.write(json.dumps(dct))


def get_new_min_id(masto) -> int:
    bookmarks = masto.bookmarks()
    # when calling `.bookmarks()`, we get by default the last bookmarks
    # and the _pagination_prev["min_id"] contains the `min_id` of the most recent bookmark
    return bookmarks._pagination_prev["min_id"]


def get_bookmarks(masto: Mastodon, min_id=None) -> List[Bookmark]:
    first_page = masto.bookmarks()

    if not min_id:
        bookmarks = masto.fetch_remaining(first_page)  # see docs fetch_remaining
    else:
        # if we have `min_id`, we can discard `first_page`, except for getting `new_min_id`
        page = masto.bookmarks(min_id=min_id)
        bookmarks = page
        while page:
            page = masto.fetch_previous(page)  # fetch_previous fetches newer toots
            bookmarks.extend(page)
    return [
        Bookmark(
            url=bookmark["url"],
            title="toot by " + bookmark["account"]["url"],
            description=bookmark["content"],
            creation_time=bookmark["created_at"],
            tags=[tag["name"] for tag in bookmark["tags"]],
        )
        for bookmark in bookmarks
    ]


def db_path() -> str:
    path = os.getenv("DB_PATH", "test.sqlite")
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
                bookmark.creation_time,
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
    log_level = os.getenv("LOG_LEVEL", "WARNING")
    path = os.getenv("LOG_PATH")
    filepath = f"{path}/{__name__}.log"
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
    min_id = get_json_state("min_id.json")
    new_min_id = get_new_min_id(masto)
    bookmarks = get_bookmarks(masto, min_id)
    insert_bookmarks(bookmarks)
    write_json_state({"min_id": new_min_id}, "min_id.json")


if __name__ == "__main__":
    cli()
