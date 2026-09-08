import json
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

        reminder_columns = {row[1] for row in self._conn.execute("PRAGMA table_info(reminders)")}
        if reminder_columns and "offset_minutes" not in reminder_columns:
            with self._conn:
                self._conn.execute("DROP TABLE reminders")

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
                    uid TEXT NOT NULL,
                    offset_minutes INTEGER NOT NULL,
                    PRIMARY KEY (uid, offset_minutes)
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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    chat_id INTEGER PRIMARY KEY,
                    reminder_offsets_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendars (
                    chat_id INTEGER NOT NULL,
                    calendar_id TEXT NOT NULL DEFAULT 'default',
                    ical_url TEXT NOT NULL,
                    PRIMARY KEY (chat_id, calendar_id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    token TEXT PRIMARY KEY,
                    occurrence_id TEXT NOT NULL
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

    def is_reminded(self, uid: str, offset_minutes: int) -> bool:
        with closing(
            self._conn.execute(
                "SELECT 1 FROM reminders WHERE uid = ? AND offset_minutes = ?", (uid, offset_minutes)
            )
        ) as cur:
            return cur.fetchone() is not None

    def mark_reminded(self, uid: str, offset_minutes: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO reminders (uid, offset_minutes) VALUES (?, ?)", (uid, offset_minutes)
            )

    def add_message(self, uid: str, chat_id: int, message_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO messages (uid, chat_id, message_id) VALUES (?, ?, ?)",
                (uid, chat_id, message_id),
            )

    def remove_message(self, chat_id: int, message_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)
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

    def get_reminder_offsets(self, chat_id: int) -> list[int] | None:
        with closing(
            self._conn.execute("SELECT reminder_offsets_json FROM settings WHERE chat_id = ?", (chat_id,))
        ) as cur:
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def set_reminder_offsets(self, chat_id: int, offsets_minutes: list[int]) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO settings (chat_id, reminder_offsets_json) VALUES (?, ?)",
                (chat_id, json.dumps(offsets_minutes)),
            )

    def clear_reminder_offsets(self, chat_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM settings WHERE chat_id = ?", (chat_id,))

    def upsert_calendar(self, chat_id: int, ical_url: str, calendar_id: str = "default") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO calendars (chat_id, calendar_id, ical_url) VALUES (?, ?, ?)",
                (chat_id, calendar_id, ical_url),
            )

    def get_calendars(self, chat_id: int) -> list[tuple[str, str]]:
        with closing(
            self._conn.execute("SELECT calendar_id, ical_url FROM calendars WHERE chat_id = ?", (chat_id,))
        ) as cur:
            return cur.fetchall()

    def get_onboarded_chat_ids(self) -> list[int]:
        with closing(self._conn.execute("SELECT DISTINCT chat_id FROM calendars")) as cur:
            return [row[0] for row in cur.fetchall()]

    def save_token(self, token: str, occurrence_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO tokens (token, occurrence_id) VALUES (?, ?)", (token, occurrence_id)
            )

    def resolve_token(self, token: str) -> str | None:
        with closing(self._conn.execute("SELECT occurrence_id FROM tokens WHERE token = ?", (token,))) as cur:
            row = cur.fetchone()
            return row[0] if row else None

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
