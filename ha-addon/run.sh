#!/usr/bin/with-contenv bashio

export SENTINEL_CONFIG_PATH="/data/options.json"
export PYTHONUNBUFFERED=1

bashio::log.info "Starting HA-Sentinel Orchestrator v$(bashio::addon.version)..."

if bashio::config.is_empty "influxdb_token"; then
    bashio::log.fatal "influxdb_token is not set. Configure it in the add-on options panel."
    exit 1
fi

if bashio::config.is_empty "telegram_bot_token"; then
    bashio::log.fatal "telegram_bot_token is not set. Configure it in the add-on options panel."
    exit 1
fi

exec python3 /app/src/main.py
