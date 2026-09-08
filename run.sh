#!/usr/bin/with-contenv bashio

export BOT_TOKEN
export CHAT_ID
export ICAL_URL
export REMINDER_OFFSETS
export POLL_INTERVAL_MINUTES
export LOOKAHEAD_DAYS
export DB_PATH=/data/gcal-bot.sqlite3

BOT_TOKEN=$(bashio::config 'bot_token')
CHAT_ID=$(bashio::config 'chat_id')
ICAL_URL=$(bashio::config 'ical_url')
REMINDER_OFFSETS=$(bashio::config 'reminder_offsets')
POLL_INTERVAL_MINUTES=$(bashio::config 'poll_interval_minutes')
LOOKAHEAD_DAYS=$(bashio::config 'lookahead_days')

cd /app
exec python3 -m bot.main
