# Changelog

## 1.5.0

- Fixed cross-group data leak: events, reminders, and RSVPs are now scoped
  per chat, not just per calendar-UID. Previously, two groups subscribed to
  the same or an overlapping calendar (e.g. a public holiday calendar) could
  suppress each other's reminders and see each other's RSVPs for what looked
  like "the same" event. Storage keys changed shape to include the chat, so
  any event whose reminder window is still open at upgrade time may get one
  extra reminder resent once (old RSVPs on it are also not carried over) —
  a one-time side effect, not an ongoing issue.

## 1.4.2

- Fixed RSVP/list buttons potentially breaking on calendars with long event
  UIDs (common with Outlook/Exchange feeds): `callback_data` now uses a
  short hash token instead of the raw event id, staying well under
  Telegram's 64-byte limit
- Fixed a double `answer()` call on expired list buttons
- `/remind` now rejects input that parses to an empty schedule instead of
  silently falling back to the default without telling you

## 1.4.1

- Fixed a burst of reminders: if several reminder windows had already
  elapsed by the first poll after `/onboard` (e.g. an event only 26 minutes
  away with `7d/1d/1h/30m` configured), all of them fired at once instead of
  just the one actually due

## 1.4.0

- Packaged as a Home Assistant Supervisor add-on (local add-on, no manual
  `docker run` needed)
- `/onboard <ical-url>`: each group connects itself to its own calendar —
  no per-group config in Home Assistant anymore
- `/next`: tappable list of upcoming events; tap one to see details and RSVP
- `/remind`: per-group reminder schedule, supports multiple offsets
  (e.g. `24h 1h 15m`), independent of the add-on's default
- `/status`: current setup, last calendar check, reminder schedule for the chat
- Welcome message (and `/start`) explaining how to use the bot when it's
  added to a group
- Translated all bot text, README, and privacy policy to English
- Fixed RSVP buttons not responding (callback parsing broke on event IDs
  containing `:`)
- Clear error message when the configured URL isn't a valid iCal feed,
  instead of a raw parser crash
- Add-on icon and logo

## 1.0.0

- Initial release: polls a Google Calendar iCal feed and posts reminders
  with Yes/No/Maybe RSVP buttons to a single configured Telegram group
