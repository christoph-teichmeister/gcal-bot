# gcal-bot

Telegram-Bot, der Termine aus einem Google-Calendar-iCal-Feed liest und
`reminder_hours_before` Stunden vor Start als Erinnerung in eine Telegram-Gruppe
postet — mit Zusage/Absage/Vielleicht-Buttons (RSVP), Teilnehmerliste live in
der Nachricht. Läuft als **Home Assistant Add-on** (Supervisor), kein separates
Docker-Gefrickel nötig.

## Setup

### 1. Telegram-Bot anlegen
1. Mit [@BotFather](https://t.me/BotFather) chatten, `/newbot`, Token notieren.
2. Bot zur Gruppe hinzufügen, Admin-Recht "Nachrichten senden" geben.
3. Chat-ID ermitteln: Bot kurz etwas in der Gruppe schreiben lassen, dann
   `https://api.telegram.org/bot<TOKEN>/getUpdates` aufrufen, `chat.id` (negative Zahl).

### 2. Google-Calendar-Feed
Google Calendar → Einstellungen → gewünschter Kalender → "Geheime Adresse im
iCal-Format" kopieren. (Geheim halten — jeder mit dem Link sieht alle Termine.)

## Als Home Assistant Add-on installieren

Supervisor erkennt jeden Ordner unter `/addons/` auf dem HAOS-Host automatisch
als lokales Add-on — kein Repository/Store-Eintrag nötig.

```bash
# lokal: Repo auf den Pi kopieren
scp -r . homeassistant:/addons/gcal-bot
```

Dann in der HA-UI:
1. **Einstellungen → Add-ons → Add-on Store → oben rechts "⋮" → Store neu laden**
2. Add-on erscheint unter "Lokale Add-ons" → installieren
3. Tab **Konfiguration**: `bot_token`, `chat_id`, `ical_url` (+ optional
   `reminder_hours_before`, `poll_interval_minutes`, `lookahead_days`) eintragen
4. Tab **Info** → Start, "Beim Systemstart starten" aktivieren

Logs direkt im Add-on-Tab "Log" einsehbar. Nach Codeänderung: erneut `scp`, dann
im Add-on-Tab "Neu erstellen" (Rebuild).

## Lokal testen (ohne HA)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=... CHAT_ID=... ICAL_URL=...
python -m bot.main
```
