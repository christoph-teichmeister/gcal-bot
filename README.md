# zocker-calendar-bot

Telegram-Bot für die Zockergruppe: liest Termine aus einem Google-Calendar-iCal-Feed,
postet `REMINDER_HOURS_BEFORE` Stunden vorher eine Erinnerung in die Gruppe mit
Zusage/Absage/Vielleicht-Buttons (RSVP), zeigt Teilnehmerliste live in der Nachricht.

## Setup

### 1. Telegram-Bot anlegen
1. Mit [@BotFather](https://t.me/BotFather) chatten, `/newbot`, Token notieren → `BOT_TOKEN`.
2. Bot zur Zockergruppe hinzufügen, ihm Admin-Recht "Nachrichten senden" geben.
3. Chat-ID der Gruppe ermitteln: Bot kurz `/start` in der Gruppe schreiben lassen, dann
   `https://api.telegram.org/bot<TOKEN>/getUpdates` aufrufen, `chat.id` (negative Zahl) → `CHAT_ID`.

### 2. Google-Calendar-Feed
Google Calendar → Einstellungen → gewünschter Kalender → "Geheime Adresse im
iCal-Format" kopieren → `ICAL_URL`. (Geheim, nicht öffentlich machen — jeder mit dem Link
sieht alle Termine.)

### 3. `.env` anlegen
```
cp .env.example .env
# Werte eintragen
```

## Deploy auf dem Home-Assistant-Server (Pi, HAOS)

HAOS-Host hat kein Python, aber einen Docker-Daemon. Bot als eigenständigen Container
neben HA laufen lassen:

```bash
# lokal: Projekt auf den Pi kopieren
scp -r . homeassistant:/root/zocker-calendar-bot

# auf dem Pi
ssh homeassistant
cd /root/zocker-calendar-bot
docker build -t zocker-calendar-bot .
docker volume create zocker-calendar-bot-data
docker run -d \
  --name zocker-calendar-bot \
  --restart unless-stopped \
  --env-file .env \
  -v zocker-calendar-bot-data:/data \
  zocker-calendar-bot
```

Logs: `ssh homeassistant "docker logs -f zocker-calendar-bot"`
Update nach Codeänderung: erneut `scp`, dann `docker build` + `docker rm -f zocker-calendar-bot` + `docker run ...` wiederholen.

## Lokal testen

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(cat .env | xargs)
python -m bot.main
```
