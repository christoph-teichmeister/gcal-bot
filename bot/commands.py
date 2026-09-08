from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.calendar_source import Occurrence, fetch_occurrences
from bot.config import Config
from bot.durations import format_minutes, parse_durations_to_minutes
from bot.handlers import build_keyboard, build_message_text
from bot.storage import Storage

MAX_UPCOMING_SHOWN = 10
LIST_TEXT = "🎲 *Upcoming events* — tap one to see it and set your RSVP:"


def _label(occurrence: Occurrence) -> str:
    start_text = occurrence.start.astimezone().strftime("%a %d.%m %H:%M")
    return f"{start_text} – {occurrence.title}"[:64]


def _build_list_keyboard(occurrences: list[Occurrence]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(_label(o), callback_data=f"show_event:{o.occurrence_id}")] for o in occurrences]
    )


async def _fetch_upcoming(config: Config) -> list[Occurrence]:
    occurrences = fetch_occurrences(config.ical_url, config.lookahead_days)
    now = datetime.now(timezone.utc)
    return sorted((o for o in occurrences if o.start >= now), key=lambda o: o.start)[:MAX_UPCOMING_SHOWN]


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]

    try:
        upcoming = await _fetch_upcoming(config)
    except Exception:
        await update.effective_message.reply_text("Couldn't load the calendar right now, try again later.")
        return

    if not upcoming:
        await update.effective_message.reply_text(f"No events in the next {config.lookahead_days} days.")
        return

    await update.effective_message.reply_text(
        LIST_TEXT, parse_mode="Markdown", reply_markup=_build_list_keyboard(upcoming)
    )


async def handle_show_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]
    _, occurrence_id = query.data.split(":", 1)

    event = storage.get_event(occurrence_id)
    if event is None:
        try:
            occurrences = fetch_occurrences(config.ical_url, config.lookahead_days)
        except Exception:
            await query.edit_message_text("Couldn't load the calendar right now, try again later.")
            return
        match = next((o for o in occurrences if o.occurrence_id == occurrence_id), None)
        if match is None:
            await query.edit_message_text("This event is no longer available.")
            return
        storage.upsert_event(match.occurrence_id, match.title, int(match.start.timestamp()), match.location)
        event = storage.get_event(occurrence_id)

    _, title, start_ts, location = event
    start_text = datetime.fromtimestamp(start_ts, tz=timezone.utc).astimezone().strftime("%a, %d.%m.%Y %H:%M")
    text = build_message_text(title, start_text, location, storage, occurrence_id)

    chat_id = query.message.chat_id
    message_id = query.message.message_id
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=build_keyboard(occurrence_id),
    )
    storage.add_message(occurrence_id, chat_id, message_id)


async def handle_show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    storage.remove_message(chat_id, message_id)

    try:
        upcoming = await _fetch_upcoming(config)
    except Exception:
        await query.edit_message_text("Couldn't load the calendar right now, try /next again later.")
        return

    if not upcoming:
        await query.edit_message_text(f"No events in the next {config.lookahead_days} days.")
        return

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=LIST_TEXT,
            parse_mode="Markdown",
            reply_markup=_build_list_keyboard(upcoming),
        )
    except BadRequest as error:
        if "not modified" not in str(error).lower():
            raise


async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        offsets = storage.get_reminder_offsets(chat_id) or config.default_reminder_offsets_minutes
        text = "Current reminders: " + ", ".join(format_minutes(m) for m in offsets)
        text += "\n\nChange with e.g. `/remind 24h 1h 15m`, reset to the default with `/remind reset`."
        await update.effective_message.reply_text(text, parse_mode="Markdown")
        return

    if len(args) == 1 and args[0].lower() == "reset":
        storage.clear_reminder_offsets(chat_id)
        await update.effective_message.reply_text("Reminders reset to the add-on's default configuration.")
        return

    try:
        offsets = parse_durations_to_minutes(" ".join(args))
    except ValueError as error:
        await update.effective_message.reply_text(
            f"Couldn't parse `{error}`. Use a number plus d/h/m, e.g. `/remind 24h 1h 15m`.",
            parse_mode="Markdown",
        )
        return

    storage.set_reminder_offsets(chat_id, offsets)
    await update.effective_message.reply_text(
        "Reminders set to: " + ", ".join(format_minutes(m) for m in offsets)
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    storage: Storage = context.bot_data["storage"]

    now = int(datetime.now(timezone.utc).timestamp())
    upcoming_count = storage.count_upcoming(now)
    last_poll = context.bot_data.get("last_poll")
    last_poll_text = last_poll.astimezone().strftime("%a, %d.%m.%Y %H:%M:%S") if last_poll else "never yet"
    offsets = storage.get_reminder_offsets(update.effective_chat.id) or config.default_reminder_offsets_minutes

    lines = [
        "🤖 *GCal Bot status*",
        "",
        f"Last calendar check: {last_poll_text}",
        f"Check interval: every {config.poll_interval_minutes:g} minutes",
        f"Reminders: {', '.join(format_minutes(m) for m in offsets)} before each event",
        f"Lookahead: {config.lookahead_days} days",
        f"Upcoming events tracked: {upcoming_count}",
    ]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
