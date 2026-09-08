import logging
from datetime import datetime, timedelta, timezone

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.calendar_source import fetch_occurrences
from bot.commands import cmd_naechste, cmd_status
from bot.config import Config
from bot.handlers import build_keyboard, build_message_text, handle_rsvp
from bot.storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("calendar_bot")


async def poll_calendar(context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]

    try:
        occurrences = fetch_occurrences(config.ical_url, config.lookahead_days)
    except Exception:
        logger.exception("Failed to fetch calendar")
        return

    now = datetime.now(timezone.utc)
    reminder_window = timedelta(hours=config.reminder_hours_before)

    for occurrence in occurrences:
        if occurrence.start - reminder_window > now:
            continue
        if occurrence.start < now:
            continue
        if storage.is_event_posted(occurrence.occurrence_id):
            continue

        start_text = occurrence.start.astimezone().strftime("%a, %d.%m.%Y %H:%M")
        text = build_message_text(occurrence.title, start_text, occurrence.location, storage, occurrence.occurrence_id)
        message = await context.bot.send_message(
            chat_id=config.chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=build_keyboard(occurrence.occurrence_id),
        )
        storage.save_posted_event(
            occurrence.occurrence_id,
            config.chat_id,
            message.message_id,
            occurrence.title,
            int(occurrence.start.timestamp()),
            occurrence.location,
        )
        logger.info("Posted reminder for %s", occurrence.title)

    cutoff = int((now - timedelta(days=1)).timestamp())
    storage.delete_events_older_than(cutoff)
    context.bot_data["last_poll"] = now


def main() -> None:
    config = Config()
    storage = Storage(config.db_path)

    application = Application.builder().token(config.bot_token).build()
    application.bot_data["config"] = config
    application.bot_data["storage"] = storage

    application.add_handler(CallbackQueryHandler(handle_rsvp, pattern=r"^rsvp:"))
    application.add_handler(CommandHandler("naechste", cmd_naechste))
    application.add_handler(CommandHandler("status", cmd_status))
    application.job_queue.run_repeating(
        poll_calendar, interval=config.poll_interval_minutes * 60, first=5
    )

    logger.info("Starting calendar bot (poll every %s min)", config.poll_interval_minutes)
    application.run_polling()


if __name__ == "__main__":
    main()
