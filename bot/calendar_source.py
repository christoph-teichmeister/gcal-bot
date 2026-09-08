from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import icalendar
import recurring_ical_events
import requests


@dataclass
class Occurrence:
    occurrence_id: str
    title: str
    start: datetime
    location: str


def fetch_occurrences(ical_url: str, lookahead_days: int) -> list[Occurrence]:
    response = requests.get(ical_url, timeout=30)
    response.raise_for_status()
    calendar = icalendar.Calendar.from_ical(response.content)

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=lookahead_days)
    events = recurring_ical_events.of(calendar).between(now, end)

    occurrences = []
    for event in events:
        start = event["DTSTART"].dt
        if not isinstance(start, datetime):
            start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        uid = str(event.get("UID", event.get("SUMMARY", "")))
        occurrence_id = f"{uid}:{int(start.timestamp())}"
        occurrences.append(
            Occurrence(
                occurrence_id=occurrence_id,
                title=str(event.get("SUMMARY", "(ohne Titel)")),
                start=start,
                location=str(event.get("LOCATION", "")),
            )
        )
    return occurrences
