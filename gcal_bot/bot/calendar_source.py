from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import icalendar
import recurring_ical_events
import requests


class InvalidIcalFeedError(Exception):
    pass


def scope_occurrence_id(chat_id: int, occurrence_id: str) -> str:
    return f"{chat_id}:{occurrence_id}"


@dataclass
class Occurrence:
    occurrence_id: str
    # Stays the same when the event is moved to a different time, unlike
    # occurrence_id (which includes the start). Used to detect reschedules.
    series_key: str
    title: str
    start: datetime
    location: str


def _to_utc(value) -> datetime:
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _recurrence_index(calendar: icalendar.Calendar) -> tuple[set[str], dict[tuple[str, int], int]]:
    """Which UIDs are recurring, and for moved instances the original slot they came from.

    recurring_ical_events drops RRULE/RECURRENCE-ID from the occurrences it
    returns, so this has to be read from the raw components.
    """
    recurring_uids: set[str] = set()
    moved_instances: dict[tuple[str, int], int] = {}
    for component in calendar.walk("VEVENT"):
        uid = str(component.get("UID", component.get("SUMMARY", "")))
        if "RRULE" in component or "RDATE" in component:
            recurring_uids.add(uid)
        if "RECURRENCE-ID" in component and "DTSTART" in component:
            recurring_uids.add(uid)
            start_ts = int(_to_utc(component["DTSTART"].dt).timestamp())
            original_ts = int(_to_utc(component["RECURRENCE-ID"].dt).timestamp())
            moved_instances[(uid, start_ts)] = original_ts
    return recurring_uids, moved_instances


def _series_key(uid: str, start_ts: int, recurring_uids: set[str], moved_instances: dict[tuple[str, int], int]) -> str:
    if uid not in recurring_uids:
        return uid
    return f"{uid}:{moved_instances.get((uid, start_ts), start_ts)}"


def fetch_occurrences(ical_url: str, lookahead_days: int) -> list[Occurrence]:
    response = requests.get(ical_url, timeout=30)
    response.raise_for_status()

    if not response.content.lstrip().startswith(b"BEGIN:VCALENDAR"):
        raise InvalidIcalFeedError(
            f"This URL did not return an iCal feed (got content-type "
            f"'{response.headers.get('Content-Type', '?')}' instead). Make sure it's the "
            f"'Secret address in iCal format' from your calendar's settings, ending in .ics."
        )

    calendar = icalendar.Calendar.from_ical(response.content)

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=lookahead_days)
    events = recurring_ical_events.of(calendar).between(now, end)
    recurring_uids, moved_instances = _recurrence_index(calendar)

    occurrences = []
    for event in events:
        start = _to_utc(event["DTSTART"].dt)
        start_ts = int(start.timestamp())

        uid = str(event.get("UID", event.get("SUMMARY", "")))
        occurrence_id = f"{uid}:{start_ts}"
        occurrences.append(
            Occurrence(
                occurrence_id=occurrence_id,
                series_key=_series_key(uid, start_ts, recurring_uids, moved_instances),
                title=str(event.get("SUMMARY", "(no title)")),
                start=start,
                location=str(event.get("LOCATION", "")),
            )
        )
    return occurrences
