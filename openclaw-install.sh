#!/usr/bin/env bash
# openclaw-install.sh
# Run INSIDE the AI LXC after ollama.sh has created and started it.
# Installs Node.js 24, OpenClaw, deploys ha-sentinel config, and registers
# OpenClaw as a systemd service.
#
# Usage:
#   bash openclaw-install.sh [path-to-openclaw-config-dir]
#
# If no path is given, it clones the repo from SENTINEL_REPO_URL.
# Set SENTINEL_REPO_URL before running, or pass the config dir as $1.

set -euo pipefail

SENTINEL_REPO_URL="${SENTINEL_REPO_URL:-https://github.com/hirofairlane/ha-sentinel-orchestrator}"
CONFIG_SRC="${1:-}"
OPENCLAW_DIR="$HOME/.openclaw"

# ── Colours ────────────────────────────────────────────────────────────────
GN='\033[1;32m'; YW='\033[33m'; RD='\033[1;31m'; CL='\033[0m'
ok()   { echo -e "${GN}✓ $*${CL}"; }
warn() { echo -e "${YW}⚠ $*${CL}"; }
die()  { echo -e "${RD}✗ $*${CL}"; exit 1; }

echo -e "\n${GN}═══ HA-Sentinel: OpenClaw Installer ═══${CL}\n"

# ── 1. Verify running inside the LXC (not on the Proxmox host) ─────────────
if [[ -f /etc/pve/version ]]; then
  die "This script must run INSIDE the LXC, not on the Proxmox host."
fi

# ── 2. Verify GPU passthrough ───────────────────────────────────────────────
echo "Checking GPU access..."
if [[ ! -c /dev/kfd ]]; then
  die "/dev/kfd not found.\n  Add to LXC config (/etc/pve/lxc/1XX.conf):\n  lxc.cgroup2.devices.allow: c 234:0 rwm\n  lxc.mount.entry: /dev/kfd dev/kfd none bind,optional,create=file\n  Then restart the LXC and re-run this script."
fi
if [[ ! -c /dev/dri/renderD129 ]]; then
  die "/dev/dri/renderD129 (AMD RX 7900 GRE) not found.\n  Add to LXC config:\n  lxc.cgroup2.devices.allow: c 226:129 rwm\n  lxc.mount.entry: /dev/dri/renderD129 dev/dri/renderD129 none bind,optional,create=file"
fi
ok "/dev/kfd and /dev/dri present — ROCm passthrough OK"

# ── 3. Verify Ollama is running ─────────────────────────────────────────────
echo "Checking Ollama..."
if ! systemctl is-active --quiet ollama 2>/dev/null; then
  warn "Ollama not running — attempting start..."
  systemctl start ollama
  sleep 3
fi
if curl -sf http://localhost:11434/api/tags >/dev/null; then
  ok "Ollama reachable at localhost:11434"
else
  die "Ollama is not responding. Check: journalctl -u ollama -n 50"
fi

# ── 4. Pull models if not present ───────────────────────────────────────────
echo "Checking Qwen 2.5 models..."
LOADED=$(curl -sf http://localhost:11434/api/tags | python3 -c "import json,sys; print([m['name'] for m in json.load(sys.stdin).get('models',[])])" 2>/dev/null || echo "[]")

if echo "$LOADED" | grep -q "qwen2.5:14b"; then
  ok "qwen2.5:14b already present"
else
  echo "Pulling qwen2.5:14b (~9 GB, this will take a while)..."
  ollama pull qwen2.5:14b
  ok "qwen2.5:14b pulled"
fi

if echo "$LOADED" | grep -q "qwen2.5:7b"; then
  ok "qwen2.5:7b already present (fallback)"
else
  echo "Pulling qwen2.5:7b (~4.5 GB fallback model)..."
  ollama pull qwen2.5:7b
  ok "qwen2.5:7b pulled"
fi

# ── 5. Install Node.js 24 ───────────────────────────────────────────────────
if command -v node &>/dev/null && node --version | grep -q "^v24"; then
  ok "Node.js $(node --version) already installed"
else
  echo "Installing Node.js 24..."
  curl -fsSL https://deb.nodesource.com/setup_24.x | bash - >/dev/null
  apt-get install -y nodejs >/dev/null
  ok "Node.js $(node --version) installed"
fi

# ── 6. Install OpenClaw ─────────────────────────────────────────────────────
if command -v openclaw &>/dev/null; then
  ok "OpenClaw already installed — skipping"
else
  echo "Installing OpenClaw..."
  curl -fsSL https://openclaw.ai/install.sh | bash
  ok "OpenClaw installed"
fi

# ── 7. Deploy ha-sentinel openclaw-config ───────────────────────────────────
echo ""
echo "Deploying ha-sentinel configuration..."

if [[ -n "$CONFIG_SRC" ]]; then
  # Local path provided (e.g. NAS mount)
  DEPLOY_SCRIPT="$CONFIG_SRC/deploy.sh"
elif [[ -n "$SENTINEL_REPO_URL" ]]; then
  # Clone from GitHub
  TMP_REPO=$(mktemp -d)
  git clone --depth 1 "$SENTINEL_REPO_URL" "$TMP_REPO"
  CONFIG_SRC="$TMP_REPO/openclaw-config"
  DEPLOY_SCRIPT="$CONFIG_SRC/deploy.sh"
else
  warn "No config source provided."
  echo "  Option A — pass local path:  bash openclaw-install.sh /path/to/openclaw-config"
  echo "  Option B — set repo URL:     SENTINEL_REPO_URL=https://github.com/ORG/REPO bash openclaw-install.sh"
  echo ""
  echo "Skipping config deploy. Run deploy.sh manually later."
  DEPLOY_SCRIPT=""
fi

if [[ -n "$DEPLOY_SCRIPT" && -f "$DEPLOY_SCRIPT" ]]; then
  bash "$DEPLOY_SCRIPT"
fi

# ── 8. Register OpenClaw as a systemd service ───────────────────────────────
SERVICE_FILE="/etc/systemd/system/openclaw.service"
ENV_FILE="$OPENCLAW_DIR/.env"

if [[ -f "$SERVICE_FILE" ]]; then
  ok "openclaw.service already exists — skipping"
else
  echo "Creating openclaw.service..."
  cat > "$SERVICE_FILE" << EOF
[Unit]
Description=OpenClaw AI Gateway
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=$OPENCLAW_DIR
EnvironmentFile=-$ENV_FILE
ExecStart=$(command -v openclaw) gateway start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=openclaw

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable openclaw
  ok "openclaw.service registered and enabled"
fi

# Start only if .env exists (secrets configured)
if [[ -f "$ENV_FILE" ]]; then
  systemctl restart openclaw
  sleep 3
  if systemctl is-active --quiet openclaw; then
    ok "OpenClaw gateway running"
  else
    warn "OpenClaw service failed to start. Check: journalctl -u openclaw -n 50"
  fi
else
  warn ".env not found at $ENV_FILE — OpenClaw not started."
  echo "  Run '$CONFIG_SRC/deploy.sh' to configure secrets, then:"
  echo "  systemctl start openclaw"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GN}═══ Installation complete ═══${CL}"
echo "  Ollama  → http://localhost:11434"
echo "  OpenClaw status → systemctl status openclaw"
echo "  OpenClaw logs   → journalctl -u openclaw -f"
echo "  Update Ollama   → bash /path/to/ollama.sh"
echo ""
