from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.storage import Storage

STATUS_LABELS = {
    "yes": "✅ Yes",
    "no": "❌ No",
    "maybe": "🤔 Maybe",
}


def build_keyboard(occurrence_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"rsvp:{occurrence_id}:yes"),
                InlineKeyboardButton("❌ No", callback_data=f"rsvp:{occurrence_id}:no"),
                InlineKeyboardButton("🤔 Maybe", callback_data=f"rsvp:{occurrence_id}:maybe"),
            ]
        ]
    )


def build_message_text(title: str, start_text: str, location: str, storage: Storage, occurrence_id: str) -> str:
    lines = [f"🎲 *{title}*", f"🕒 {start_text}"]
    if location:
        lines.append(f"📍 {location}")

    rsvps = storage.get_rsvps(occurrence_id)
    by_status: dict[str, list[str]] = {"yes": [], "no": [], "maybe": []}
    for user_name, status in rsvps:
        by_status.setdefault(status, []).append(user_name)

    lines.append("")
    for status, label in STATUS_LABELS.items():
        names = ", ".join(by_status.get(status, [])) or "–"
        lines.append(f"{label}: {names}")

    return "\n".join(lines)


async def refresh_event_messages(context: ContextTypes.DEFAULT_TYPE, storage: Storage, occurrence_id: str) -> None:
    event = storage.get_event(occurrence_id)
    if event is None:
        return
    _, title, start_ts, location = event

    start_text = datetime.fromtimestamp(start_ts, tz=timezone.utc).astimezone().strftime("%a, %d.%m.%Y %H:%M")
    text = build_message_text(title, start_text, location, storage, occurrence_id)
    keyboard = build_keyboard(occurrence_id)

    for chat_id, message_id in storage.get_messages(occurrence_id):
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except BadRequest as error:
            if "not modified" not in str(error).lower():
                raise


async def handle_rsvp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    storage: Storage = context.bot_data["storage"]

    _, rest = query.data.split(":", 1)
    occurrence_id, status = rest.rsplit(":", 1)
    user = query.from_user
    user_name = user.full_name or user.username or str(user.id)

    storage.set_rsvp(occurrence_id, user.id, user_name, status)
    await query.answer(f"Saved: {STATUS_LABELS[status]}")

    await refresh_event_messages(context, storage, occurrence_id)
