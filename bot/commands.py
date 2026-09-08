from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.calendar_source import fetch_occurrences
from bot.config import Config
from bot.storage import Storage

MAX_UPCOMING_SHOWN = 5


async def cmd_naechste(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]

    try:
        occurrences = fetch_occurrences(config.ical_url, config.lookahead_days)
    except Exception:
        await update.effective_message.reply_text("Konnte Kalender gerade nicht laden, versuch's später nochmal.")
        return

    now = datetime.now(timezone.utc)
    upcoming = sorted((o for o in occurrences if o.start >= now), key=lambda o: o.start)[:MAX_UPCOMING_SHOWN]

    if not upcoming:
        await update.effective_message.reply_text(f"Keine Termine in den nächsten {config.lookahead_days} Tagen.")
        return

    lines = ["🎲 *Nächste Termine:*", ""]
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
    last_poll_text = last_poll.astimezone().strftime("%a, %d.%m.%Y %H:%M:%S") if last_poll else "noch nie"

    lines = [
        "🤖 *GCal Bot Status*",
        "",
        f"Letzter Kalender-Check: {last_poll_text}",
        f"Check-Intervall: alle {config.poll_interval_minutes:g} Minuten",
        f"Erinnerung: {config.reminder_hours_before:g} Std vor Termin",
        f"Vorausschau: {config.lookahead_days} Tage",
        f"Bereits gepostete, anstehende Termine: {upcoming_count}",
    ]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
