#!/usr/bin/env bash
# Deploys openclaw-config/workspace/ to ~/.openclaw/workspace/
# and creates ~/.openclaw/openclaw.json5 from the template,
# prompting for real secrets. Run once on the AI LXC.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
mkdir -p "$OPENCLAW_DIR/workspace/skills"

echo "==> Copying workspace (agents, skills)..."
cp -r "$REPO_DIR/workspace/." "$OPENCLAW_DIR/workspace/"

CONFIG_DEST="$OPENCLAW_DIR/openclaw.json5"
if [[ -f "$CONFIG_DEST" ]]; then
  echo "==> $CONFIG_DEST already exists — skipping (delete it to regenerate)."
else
  echo "==> Generating $CONFIG_DEST from template..."
  cp "$REPO_DIR/config.json5" "$CONFIG_DEST"

  read -rp "Telegram bot token: " TG_TOKEN
  read -rp "Telegram allowed chat IDs (comma-separated): " TG_CHATS
  read -rp "HA URL (e.g. http://192.168.1.x:8123): " HA_URL
  read -rp "HA long-lived token: " HA_TOKEN
  read -rp "InfluxDB URL (e.g. http://192.168.1.x:8086): " INFLUX_URL
  read -rp "InfluxDB token: " INFLUX_TOKEN
  read -rp "InfluxDB org: " INFLUX_ORG

  sed -i \
    -e "s|{{TELEGRAM_BOT_TOKEN}}|$TG_TOKEN|g" \
    -e "s|{{TELEGRAM_ALLOWED_CHAT_IDS}}|$TG_CHATS|g" \
    "$CONFIG_DEST"

  # Write env file for OpenClaw systemd service (sourced at startup)
  ENV_FILE="$OPENCLAW_DIR/.env"
  cat > "$ENV_FILE" << ENVEOF
HA_URL=$HA_URL
HA_TOKEN=$HA_TOKEN
INFLUXDB_URL=$INFLUX_URL
INFLUXDB_TOKEN=$INFLUX_TOKEN
INFLUXDB_ORG=$INFLUX_ORG
ENVEOF
  chmod 600 "$ENV_FILE"
  echo "==> Secrets written to $ENV_FILE (chmod 600)"
fi

echo "==> Done. Start OpenClaw with: openclaw gateway start"
