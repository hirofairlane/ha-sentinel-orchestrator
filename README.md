# HA-Sentinel Orchestrator

Local-first agentic AI system for Home Assistant.

**Muscle:** Ollama + OpenClaw on a Proxmox LXC (AMD RX 7900 GRE / ROCm)
**Brain:** Python 3.12 asyncio Add-on inside Home Assistant

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical reference.

## Quick Start

1. Deploy Ollama + OpenClaw on the LXC — see ARCHITECTURE.md §11
2. Install the Add-on in Home Assistant and fill the options panel
3. Send `/status` on Telegram to verify all systems are green

## Configuration

All sensitive values (tokens, IPs, bucket names) are set exclusively through
the Home Assistant Add-on options panel. No secrets are stored in this repository.
