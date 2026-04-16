#!/usr/bin/env bash
# proxmox-gpu-passthrough.sh
# Run on the PROXMOX HOST (Zeratul) after ollama.sh has created the AI LXC.
# Adds the correct AMD RX 7900 GRE device passthrough lines to the LXC config.
#
# Usage:  bash proxmox-gpu-passthrough.sh <LXCID>
# Example: bash proxmox-gpu-passthrough.sh 102

set -euo pipefail

LXCID="${1:-}"
[[ -z "$LXCID" ]] && { echo "Usage: $0 <LXCID>"; exit 1; }

CONF="/etc/pve/lxc/${LXCID}.conf"
[[ ! -f "$CONF" ]] && { echo "ERROR: $CONF not found. Is the LXC ID correct?"; exit 1; }

# ── Detect AMD GPU devices on THIS host ────────────────────────────────────
echo "Detecting AMD GPU devices on host..."

AMD_RENDER=""
for node in /sys/class/drm/renderD*/device/uevent; do
  if grep -q "PCI_ID=1002:" "$node" 2>/dev/null; then
    DEV=$(basename "$(dirname "$(dirname "$node")")")   # e.g. renderD129
    AMD_RENDER="/dev/dri/$DEV"
    break
  fi
done

[[ -z "$AMD_RENDER" ]] && { echo "ERROR: No AMD GPU found in /sys/class/drm/"; exit 1; }

# Get major:minor for the AMD renderD device
RENDER_MAJOR=$(stat -c '%t' "$AMD_RENDER" | xargs printf '%d')   # hex → dec
RENDER_MINOR=$(stat -c '%T' "$AMD_RENDER" | xargs printf '%d')

# Get major:minor for /dev/kfd
[[ ! -c /dev/kfd ]] && { echo "ERROR: /dev/kfd not found. Is amdgpu loaded on the host?"; exit 1; }
KFD_MAJOR=$(stat -c '%t' /dev/kfd | xargs printf '%d')
KFD_MINOR=$(stat -c '%T' /dev/kfd | xargs printf '%d')

echo "  AMD render node : $AMD_RENDER  ($RENDER_MAJOR:$RENDER_MINOR)"
echo "  /dev/kfd        : ($KFD_MAJOR:$KFD_MINOR)"

# ── Check if already configured ────────────────────────────────────────────
if grep -q "renderD" "$CONF" 2>/dev/null; then
  echo "WARNING: GPU passthrough lines already present in $CONF — skipping."
  echo "  Remove them manually if you want to re-apply."
  exit 0
fi

# ── Stop LXC if running ────────────────────────────────────────────────────
if pct status "$LXCID" | grep -q "running"; then
  echo "Stopping LXC $LXCID..."
  pct stop "$LXCID"
fi

# ── Append passthrough config ──────────────────────────────────────────────
echo "" >> "$CONF"
echo "# AMD RX 7900 GRE — ROCm passthrough (added by proxmox-gpu-passthrough.sh)" >> "$CONF"
echo "lxc.cgroup2.devices.allow: c ${RENDER_MAJOR}:${RENDER_MINOR} rwm" >> "$CONF"
echo "lxc.cgroup2.devices.allow: c ${KFD_MAJOR}:${KFD_MINOR} rwm"       >> "$CONF"
echo "lxc.mount.entry: ${AMD_RENDER} dev/dri/$(basename $AMD_RENDER) none bind,optional,create=file" >> "$CONF"
echo "lxc.mount.entry: /dev/kfd dev/kfd none bind,optional,create=file"  >> "$CONF"

echo ""
echo "Added to $CONF:"
tail -6 "$CONF"

# ── Start LXC ─────────────────────────────────────────────────────────────
echo ""
echo "Starting LXC $LXCID..."
pct start "$LXCID"
sleep 4

echo ""
echo "Verifying GPU inside LXC..."
if pct exec "$LXCID" -- ls /dev/kfd /dev/dri/$(basename $AMD_RENDER) 2>/dev/null; then
  echo "✓ GPU devices visible inside LXC $LXCID"
else
  echo "✗ Devices not visible yet — check: pct exec $LXCID -- ls /dev/dri/ /dev/kfd"
fi

echo ""
echo "Done. Next step — inside LXC $LXCID:"
echo "  pct exec $LXCID -- bash /path/to/openclaw-install.sh"
