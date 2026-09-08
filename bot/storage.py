import sqlite3
from contextlib import closing


class Storage:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate_legacy_schema()
        self._init_schema()

    def _migrate_legacy_schema(self) -> None:
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(events)")}
        if "chat_id" in columns:
            with self._conn:
                self._conn.execute("DROP TABLE events")
                self._conn.execute("DROP TABLE IF EXISTS rsvps")

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    uid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_ts INTEGER NOT NULL,
                    location TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    uid TEXT PRIMARY KEY
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    uid TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    PRIMARY KEY (uid, chat_id, message_id)
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

    def upsert_event(self, uid: str, title: str, start_ts: int, location: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO events (uid, title, start_ts, location) VALUES (?, ?, ?, ?)",
                (uid, title, start_ts, location),
            )

    def get_event(self, uid: str):
        with closing(
            self._conn.execute("SELECT uid, title, start_ts, location FROM events WHERE uid = ?", (uid,))
        ) as cur:
            return cur.fetchone()

    def is_reminded(self, uid: str) -> bool:
        with closing(self._conn.execute("SELECT 1 FROM reminders WHERE uid = ?", (uid,))) as cur:
            return cur.fetchone() is not None

    def mark_reminded(self, uid: str) -> None:
        with self._conn:
            self._conn.execute("INSERT OR IGNORE INTO reminders (uid) VALUES (?)", (uid,))

    def add_message(self, uid: str, chat_id: int, message_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO messages (uid, chat_id, message_id) VALUES (?, ?, ?)",
                (uid, chat_id, message_id),
            )

    def get_messages(self, uid: str) -> list[tuple[int, int]]:
        with closing(self._conn.execute("SELECT chat_id, message_id FROM messages WHERE uid = ?", (uid,))) as cur:
            return cur.fetchall()

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
            params = [(u,) for u in old_uids]
            self._conn.executemany("DELETE FROM events WHERE uid = ?", params)
            self._conn.executemany("DELETE FROM reminders WHERE uid = ?", params)
            self._conn.executemany("DELETE FROM messages WHERE uid = ?", params)
            self._conn.executemany("DELETE FROM rsvps WHERE uid = ?", params)
