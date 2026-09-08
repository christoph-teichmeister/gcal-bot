import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler, ContextTypes

from bot.calendar_source import fetch_occurrences
from bot.commands import (
    cmd_next,
    cmd_onboard,
    cmd_remind,
    cmd_start,
    cmd_status,
    handle_bot_membership,
    handle_show_event,
    handle_show_list,
)
from bot.config import Config
from bot.durations import format_minutes
from bot.handlers import build_keyboard, build_message_text, handle_rsvp
from bot.storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("calendar_bot")


async def poll_chat(context: ContextTypes.DEFAULT_TYPE, config: Config, storage: Storage, chat_id: int) -> None:
    occurrences = []
    for _, ical_url in storage.get_calendars(chat_id):
        occurrences.extend(fetch_occurrences(ical_url, config.lookahead_days))

    now = datetime.now(timezone.utc)
    offsets = storage.get_reminder_offsets(chat_id) or config.default_reminder_offsets_minutes

    for occurrence in occurrences:
        if occurrence.start < now:
            continue

        for offset_minutes in offsets:
            window_start = occurrence.start - timedelta(minutes=offset_minutes)
            if window_start > now:
                continue
            if storage.is_reminded(occurrence.occurrence_id, offset_minutes):
                continue

            stale_after = timedelta(minutes=config.poll_interval_minutes * 2)
            if now - window_start > stale_after:
                storage.mark_reminded(occurrence.occurrence_id, offset_minutes)
                logger.info(
                    "Skipped stale %s reminder for %s in chat %s (window opened %s ago)",
                    format_minutes(offset_minutes),
                    occurrence.title,
                    chat_id,
                    now - window_start,
                )
                continue

            storage.upsert_event(
                occurrence.occurrence_id, occurrence.title, int(occurrence.start.timestamp()), occurrence.location
            )
            start_text = occurrence.start.astimezone().strftime("%a, %d.%m.%Y %H:%M")
            header = f"⏰ *{format_minutes(offset_minutes)} reminder*\n"
            text = header + build_message_text(
                occurrence.title, start_text, occurrence.location, storage, occurrence.occurrence_id
            )
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=build_keyboard(occurrence.occurrence_id, storage),
            )
            storage.add_message(occurrence.occurrence_id, chat_id, message.message_id)
            storage.mark_reminded(occurrence.occurrence_id, offset_minutes)
            logger.info("Posted %s reminder for %s in chat %s", format_minutes(offset_minutes), occurrence.title, chat_id)

    cutoff = int((now - timedelta(days=1)).timestamp())
    storage.delete_events_older_than(cutoff)


async def poll_calendar(context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]

    for chat_id in storage.get_onboarded_chat_ids():
        try:
            await poll_chat(context, config, storage, chat_id)
        except Exception:
            logger.exception("Failed to poll calendar for chat %s", chat_id)

    context.bot_data["last_poll"] = datetime.now(timezone.utc)


def main() -> None:
    config = Config()
    storage = Storage(config.db_path)

    application = Application.builder().token(config.bot_token).build()
    application.bot_data["config"] = config
    application.bot_data["storage"] = storage

    application.add_handler(CallbackQueryHandler(handle_rsvp, pattern=r"^rsvp:"))
    application.add_handler(CallbackQueryHandler(handle_show_event, pattern=r"^show_event:"))
    application.add_handler(CallbackQueryHandler(handle_show_list, pattern=r"^show_list$"))
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("onboard", cmd_onboard))
    application.add_handler(CommandHandler("next", cmd_next))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("remind", cmd_remind))
    application.add_handler(ChatMemberHandler(handle_bot_membership, ChatMemberHandler.MY_CHAT_MEMBER))
    application.job_queue.run_repeating(
        poll_calendar, interval=config.poll_interval_minutes * 60, first=5
    )

    logger.info("Starting calendar bot (poll every %s min)", config.poll_interval_minutes)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
