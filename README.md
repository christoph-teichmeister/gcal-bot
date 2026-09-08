# gcal-bot

Telegram bot that reads events from a Google Calendar iCal feed and posts
reminders to a Telegram group before each event starts — with Yes/No/Maybe
RSVP buttons, live participant list in the message. Supports multiple
reminders per event (e.g. 24h, 1h, 15m before). Runs as a **Home Assistant
add-on** (Supervisor), no manual Docker juggling needed.

## Commands

- `/next` — list upcoming events; tap one to see its details and set your RSVP
- `/remind` — show the reminder schedule for this group; `/remind 24h 1h 15m`
  changes it, `/remind reset` goes back to the add-on's default
- `/status` — last calendar check, current config, number of upcoming events
  tracked

Register them with BotFather via `/setcommands` so they show up in the "/"
menu:
```
next - Show upcoming events
remind - View or change the reminder schedule
status - Show bot status
```

## Setup

### 1. Create a Telegram bot
1. Chat with [@BotFather](https://t.me/BotFather), `/newbot`, note the token.
2. Add the bot to the group, give it the "send messages" admin right.
3. Get the chat ID: have the bot see any message in the group, then call
   `https://api.telegram.org/bot<TOKEN>/getUpdates`, read `chat.id` (a negative
   number).

### 2. Google Calendar feed
Google Calendar → Settings → the calendar you want → "Secret address in iCal
format" → copy it. (Keep it secret — anyone with the link sees every event.)

## Install as a Home Assistant add-on

Supervisor auto-detects any folder under `/addons/` on the HAOS host as a
local add-on — no repository/store entry needed.

```bash
# locally: copy the repo to the Pi
scp -r . homeassistant:/addons/gcal-bot
```

Then in the HA UI:
1. **Settings → Add-ons → Add-on Store → top-right "⋮" → Reload the store**
2. The add-on shows up under "Local add-ons" → install it
3. **Configuration** tab: fill in `bot_token`, `chat_id`, `ical_url` (plus
   optionally `reminder_offsets` — comma/space-separated durations like
   `24h,1h,15m` — `poll_interval_minutes`, `lookahead_days`). The group can
   override `reminder_offsets` at runtime with `/remind`, without touching this
   config.
4. **Info** tab → Start, enable "Start on boot"

Logs are visible right in the add-on's "Log" tab. After a code change: `scp`
again, then hit "Rebuild" in the add-on tab.

## Test locally (without HA)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=... CHAT_ID=... ICAL_URL=...
python -m bot.main
```
