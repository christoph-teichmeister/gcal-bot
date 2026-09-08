import sqlite3
from contextlib import closing


class Storage:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    uid TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    start_ts INTEGER NOT NULL,
                    location TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rsvps (
                    uid TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    user_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (uid, user_id)
                )
                """
            )

    def is_event_posted(self, uid: str) -> bool:
        with closing(self._conn.execute("SELECT 1 FROM events WHERE uid = ?", (uid,))) as cur:
            return cur.fetchone() is not None

    def save_posted_event(
        self, uid: str, chat_id: int, message_id: int, title: str, start_ts: int, location: str
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO events (uid, chat_id, message_id, title, start_ts, location) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (uid, chat_id, message_id, title, start_ts, location),
            )

    def get_event(self, uid: str):
        with closing(
            self._conn.execute(
                "SELECT uid, chat_id, message_id, title, start_ts, location FROM events WHERE uid = ?", (uid,)
            )
        ) as cur:
            return cur.fetchone()

    def set_rsvp(self, uid: str, user_id: int, user_name: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO rsvps (uid, user_id, user_name, status) VALUES (?, ?, ?, ?)",
                (uid, user_id, user_name, status),
            )

    def get_rsvps(self, uid: str) -> list[tuple[str, str]]:
        with closing(
            self._conn.execute("SELECT user_name, status FROM rsvps WHERE uid = ? ORDER BY user_name", (uid,))
        ) as cur:
            return cur.fetchall()

    def count_upcoming(self, ts: int) -> int:
        with closing(self._conn.execute("SELECT COUNT(*) FROM events WHERE start_ts >= ?", (ts,))) as cur:
            return cur.fetchone()[0]

    def delete_events_older_than(self, ts: int) -> None:
        with self._conn:
            old_uids = [row[0] for row in self._conn.execute("SELECT uid FROM events WHERE start_ts < ?", (ts,))]
            if not old_uids:
                return
            self._conn.executemany("DELETE FROM events WHERE uid = ?", [(u,) for u in old_uids])
            self._conn.executemany("DELETE FROM rsvps WHERE uid = ?", [(u,) for u in old_uids])
