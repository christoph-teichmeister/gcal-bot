import re

_DURATION_RE = re.compile(r"^(\d+)\s*([dhm])$", re.IGNORECASE)
_UNIT_MINUTES = {"d": 1440, "h": 60, "m": 1}


def parse_duration_to_minutes(token: str) -> int:
    match = _DURATION_RE.match(token.strip())
    if not match:
        raise ValueError(token)
    value, unit = match.groups()
    return int(value) * _UNIT_MINUTES[unit.lower()]


def parse_durations_to_minutes(raw: str) -> list[int]:
    tokens = [t for t in re.split(r"[,\s]+", raw.strip()) if t]
    return sorted({parse_duration_to_minutes(t) for t in tokens}, reverse=True)


def format_minutes(minutes: int) -> str:
    if minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"
