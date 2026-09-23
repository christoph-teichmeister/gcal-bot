import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler, ContextTypes

from bot.calendar_source import Occurrence, fetch_occurrences, scope_occurrence_id
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
from bot.handlers import build_keyboard, build_message_text, handle_rsvp, refresh_event_messages
from bot.storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("calendar_bot")


def _format_start(start: datetime) -> str:
    return start.astimezone().strftime("%a, %d.%m.%Y %H:%M")


async def handle_reschedule(
    context: ContextTypes.DEFAULT_TYPE,
    storage: Storage,
    chat_id: int,
    occurrence: Occurrence,
    offsets: list[int],
    now: datetime,
) -> None:
    """Detect that an event was moved in the calendar and carry its chat state over to the new time."""
    scoped_id = scope_occurrence_id(chat_id, occurrence.occurrence_id)
    start_ts = int(occurrence.start.timestamp())
    tracked = storage.get_tracked_occurrence(chat_id, occurrence.series_key)
    storage.track_occurrence(chat_id, occurrence.series_key, scoped_id, start_ts)
    if tracked is None or tracked[0] == scoped_id:
        return

    old_id, old_start_ts = tracked
    announced = storage.has_activity(old_id)
    storage.move_occurrence(old_id, scoped_id)
    storage.upsert_event(scoped_id, occurrence.title, start_ts, occurrence.location)
    old_start_text = _format_start(datetime.fromtimestamp(old_start_ts, tz=timezone.utc))
    logger.info("%s in chat %s moved from %s to %s", occurrence.title, chat_id, old_start_text, occurrence.start)

    # Nobody in the chat has seen or answered this event yet: the regular
    # reminder will show the new time, no need for a separate notice.
    if not announced:
        return

    try:
        await refresh_event_messages(context, storage, scoped_id)
    except Exception:
        logger.exception("Failed to update old messages for moved event %s in chat %s", occurrence.title, chat_id)

    header = f"📅 *Rescheduled* (was {old_start_text})\n"
    text = header + build_message_text(
        occurrence.title, _format_start(occurrence.start), occurrence.location, storage, scoped_id
    )
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=build_keyboard(scoped_id, storage),
    )
    storage.add_message(scoped_id, chat_id, message.message_id)

    # The notice replaces any reminder for the new time that's already due.
    for offset_minutes in offsets:
        if occurrence.start - timedelta(minutes=offset_minutes) <= now:
            storage.mark_reminded(scoped_id, offset_minutes)


async def poll_chat(context: ContextTypes.DEFAULT_TYPE, config: Config, storage: Storage, chat_id: int) -> None:
    occurrences = []
    for _, ical_url in storage.get_calendars(chat_id):
        occurrences.extend(fetch_occurrences(ical_url, config.lookahead_days))

    now = datetime.now(timezone.utc)
    offsets = storage.get_reminder_offsets(chat_id) or config.default_reminder_offsets_minutes

    for occurrence in occurrences:
        if occurrence.start < now:
            continue

        await handle_reschedule(context, storage, chat_id, occurrence, offsets, now)
        scoped_id = scope_occurrence_id(chat_id, occurrence.occurrence_id)

        for offset_minutes in offsets:
            window_start = occurrence.start - timedelta(minutes=offset_minutes)
            if window_start > now:
                continue
            if storage.is_reminded(scoped_id, offset_minutes):
                continue

            stale_after = timedelta(minutes=config.poll_interval_minutes * 2)
            if now - window_start > stale_after:
                storage.mark_reminded(scoped_id, offset_minutes)
                logger.info(
                    "Skipped stale %s reminder for %s in chat %s (window opened %s ago)",
                    format_minutes(offset_minutes),
                    occurrence.title,
                    chat_id,
                    now - window_start,
                )
                continue

            storage.upsert_event(scoped_id, occurrence.title, int(occurrence.start.timestamp()), occurrence.location)
            start_text = _format_start(occurrence.start)
            header = f"⏰ *{format_minutes(offset_minutes)} reminder*\n"
            text = header + build_message_text(occurrence.title, start_text, occurrence.location, storage, scoped_id)
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=build_keyboard(scoped_id, storage),
            )
            storage.add_message(scoped_id, chat_id, message.message_id)
            storage.mark_reminded(scoped_id, offset_minutes)
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
