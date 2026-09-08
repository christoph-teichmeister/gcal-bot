from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.calendar_source import fetch_occurrences
from bot.config import Config
from bot.storage import Storage

MAX_UPCOMING_SHOWN = 5


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]

    try:
        occurrences = fetch_occurrences(config.ical_url, config.lookahead_days)
    except Exception:
        await update.effective_message.reply_text("Couldn't load the calendar right now, try again later.")
        return

    now = datetime.now(timezone.utc)
    upcoming = sorted((o for o in occurrences if o.start >= now), key=lambda o: o.start)[:MAX_UPCOMING_SHOWN]

    if not upcoming:
        await update.effective_message.reply_text(f"No events in the next {config.lookahead_days} days.")
        return

    lines = ["🎲 *Upcoming events:*", ""]
    for occurrence in upcoming:
        start_text = occurrence.start.astimezone().strftime("%a, %d.%m.%Y %H:%M")
        line = f"🕒 {start_text} – {occurrence.title}"
        if occurrence.location:
            line += f" (📍 {occurrence.location})"
        lines.append(line)

    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]

    now = int(datetime.now(timezone.utc).timestamp())
    upcoming_count = storage.count_upcoming(now)
    last_poll = context.bot_data.get("last_poll")
    last_poll_text = last_poll.astimezone().strftime("%a, %d.%m.%Y %H:%M:%S") if last_poll else "never yet"

    lines = [
        "🤖 *GCal Bot status*",
        "",
        f"Last calendar check: {last_poll_text}",
        f"Check interval: every {config.poll_interval_minutes:g} minutes",
        f"Reminder: {config.reminder_hours_before:g} hours before event",
        f"Lookahead: {config.lookahead_days} days",
        f"Upcoming events already posted: {upcoming_count}",
    ]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
