import os

from bot.durations import parse_durations_to_minutes


class Config:
    def __init__(self) -> None:
        self.bot_token = self._require("BOT_TOKEN")
        self.default_reminder_offsets_minutes = parse_durations_to_minutes(
            os.environ.get("REMINDER_OFFSETS", "24h")
        )
        self.poll_interval_minutes = float(os.environ.get("POLL_INTERVAL_MINUTES", "15"))
        self.lookahead_days = int(os.environ.get("LOOKAHEAD_DAYS", "30"))
        self.db_path = os.environ.get("DB_PATH", "/data/calendar-bot.sqlite3")

    @staticmethod
    def _require(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Environment variable {name} is required")
        return value
