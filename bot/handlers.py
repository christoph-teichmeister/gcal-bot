import hashlib
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

EXPIRED_TEXT = "This button has expired, run /next again to get a fresh list."


def occurrence_token(occurrence_id: str) -> str:
    return hashlib.sha1(occurrence_id.encode()).hexdigest()[:12]


def build_keyboard(occurrence_id: str, storage: Storage) -> InlineKeyboardMarkup:
    token = occurrence_token(occurrence_id)
    storage.save_token(token, occurrence_id)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"rsvp:{token}:yes"),
                InlineKeyboardButton("❌ No", callback_data=f"rsvp:{token}:no"),
                InlineKeyboardButton("🤔 Maybe", callback_data=f"rsvp:{token}:maybe"),
            ],
            [InlineKeyboardButton("📋 Upcoming events", callback_data="show_list")],
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
    keyboard = build_keyboard(occurrence_id, storage)

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

    _, token, status = query.data.split(":", 2)
    occurrence_id = storage.resolve_token(token)
    if occurrence_id is None:
        await query.answer(EXPIRED_TEXT, show_alert=True)
        return

    user = query.from_user
    user_name = user.full_name or user.username or str(user.id)

    storage.set_rsvp(occurrence_id, user.id, user_name, status)
    await query.answer(f"Saved: {STATUS_LABELS[status]}")

    await refresh_event_messages(context, storage, occurrence_id)
