# HA-Sentinel Orchestrator — Architecture Reference

> **Version:** 0.2.0 | **Last updated:** 2026-04-16
> **Logs:** English (US) structured JSON · **UI:** Spanish (Spain)

---

## 1. Executive Summary

HA-Sentinel is a local-first agentic AI system built on a clean two-tier separation:

| Tier | Role | Where |
|---|---|---|
| **AI LXC** | Inference + Agent orchestration | Proxmox LXC (dedicated) |
| **HA Add-on** | Health monitoring + Alexa endpoint | HAOS Docker add-on |

OpenClaw is the primary agent runtime. It handles all intelligence, Telegram UI,
Home Assistant control, and InfluxDB writes directly.
The Python add-on is intentionally minimal — health checks and Alexa only.

---

## 2. Infrastructure Diagram

```
╔══════════════════════════════════════════════════════════════════════════╗
║  PROXMOX HOST — Zeratul  (i5-14400 · 64 GB RAM · RX 7900 GRE 16 GB)   ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │  LXC 101 — Plex                                                  │   ║
║  │  Intel UHD 730 (iGPU) ← hardware transcoding                    │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │  LXC 1XX — AI  (privileged, Debian 12)                          │   ║
║  │  RX 7900 GRE 16 GB VRAM ← EXCLUSIVE, /dev/kfd + /dev/dri        │   ║
║  │                                                                  │   ║
║  │  ┌──────────────────────────────────────────────────────────┐   │   ║
║  │  │  Ollama  :11434                                          │   │   ║
║  │  │  Model: qwen2.5:14b  (~9 GB VRAM, hot-loaded)           │   │   ║
║  │  │  Fallback: qwen2.5:7b                                    │   │   ║
║  │  │  Backend: ROCm 6.x                                       │   │   ║
║  │  └──────────────────────┬───────────────────────────────────┘   │   ║
║  │                         │ localhost:11434                        │   ║
║  │  ┌──────────────────────▼───────────────────────────────────┐   │   ║
║  │  │  OpenClaw Gateway  (Node.js 24, systemd)                 │   │   ║
║  │  │                                                          │   │   ║
║  │  │  ┌──────────────┐  ┌────────────┐  ┌─────────────────┐  │   │   ║
║  │  │  │ Telegram     │  │  Ollama    │  │  Agent Pool     │  │   │   ║
║  │  │  │ (grammY)     │  │  Provider  │  │  AGENTS.md      │  │   │   ║
║  │  │  │ streaming    │  │  api:ollama│  │  SOUL.md        │  │   │   ║
║  │  │  │ whitelist    │  └────────────┘  └─────────────────┘  │   │   ║
║  │  │  └──────────────┘                                        │   │   ║
║  │  │                                                          │   │   ║
║  │  │  Skills:                                                 │   │   ║
║  │  │  ha-light ─────────► POST HAOS:8123/api/services/light  │   │   ║
║  │  │  ha-climate ────────► POST HAOS:8123/api/services/climate│   │   ║
║  │  │  ha-status ─────────► GET  HAOS:8123/api/states         │   │   ║
║  │  │  ha-history ─────────► Qwen genera Flux ──► HAOS:8086   │   │   ║
║  │  └──────────────────────────────────────────────────────────┘   │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐   ║
║  │  HAOS VM                                                         │   ║
║  │                                                                  │   ║
║  │  ┌────────────────────┐   ┌──────────────────────────────────┐  │   ║
║  │  │  HA Core  :8123    │   │  ha-sentinel Add-on (Python)     │  │   ║
║  │  └────────────────────┘   │                                  │  │   ║
║  │  ┌────────────────────┐   │  Health Check daemon 60s         │  │   ║
║  │  │  InfluxDB  :8086   │   │  ├─ Ollama /api/tags             │  │   ║
║  │  └────────────────────┘   │  ├─ HA Supervisor /core/info     │  │   ║
║  │  ┌────────────────────┐   │  ├─ InfluxDB client.ping()       │  │   ║
║  │  │  Grafana           │   │  └─ Telegram Bot.get_me()        │  │   ║
║  │  │  (dashboards)      │   │                                  │  │   ║
║  │  └────────────────────┘   │  Alexa Endpoint  :8099           │  │   ║
║  │                           │  POST /alexa → Ollama → response │  │   ║
║  │                           └──────────────────────────────────┘  │   ║
║  └──────────────────────────────────────────────────────────────────┘   ║
║                                                                          ║
║  External:                                                               ║
║    Telegram Cloud ──────► OpenClaw (LXC)                                ║
║    Alexa Cloud    ──────► ha-sentinel Add-on :8099                       ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 3. Component Responsibilities

### 3.1 Ollama (AI LXC)
- Serves Qwen 2.5 14B via `/api/chat` on `localhost:11434`.
- ROCm 6.x backend, RX 7900 GRE exclusively (Plex uses Intel iGPU).
- Model stays hot-loaded in VRAM; cold-start only on explicit `/reload`.
- **Never exposed to WAN.** Bound to `127.0.0.1` inside the LXC.

### 3.2 OpenClaw Gateway (AI LXC)
The primary agent runtime. Owns all intelligence and HA interaction.

| Responsibility | How |
|---|---|
| Multi-agent pool | `AGENTS.md` + `SOUL.md` in workspace |
| Model inference | Ollama provider, `api: "ollama"` (native tool calling) |
| Telegram interface | grammY — streaming, inline keyboards, `allowed_chat_ids` whitelist |
| Agent lifecycle | `/start`, `/stop`, `/reload` commands |
| HA light control | `ha-light` skill → HA REST API |
| HA climate control | `ha-climate` skill → HA REST API |
| Home status snapshot | `ha-status` skill → HA REST API |
| Historical data query | `ha-history` skill — Qwen generates Flux → InfluxDB |
| Metrics (TTFT/TPS) | Written directly to InfluxDB by `ha-metrics` skill |
| Conversation memory | Written to InfluxDB by `ha-memory` skill |

### 3.3 ha-sentinel Add-on (HAOS — Python 3.12)
Intentionally minimal. Does only what cannot be done from the LXC.

| Module | Purpose |
|---|---|
| `health.py` | Polls Ollama, HA Supervisor, InfluxDB, Telegram every 60 s; writes results to InfluxDB; alerts admin Telegram chat on failure |
| `alexa.py` | HTTP endpoint :8099 — receives text from Alexa, calls Ollama directly, returns plain-text response |

### 3.4 InfluxDB + Grafana (HAOS)
Off-the-shelf analytics stack. No custom Python analytics unless a specific
dashboard requirement cannot be met with Flux queries and Grafana panels.

| Bucket | Content |
|---|---|
| `ha_sentinel_metrics` | TTFT, TPS, token counts, health check latencies |
| `ha_sentinel_memory` | Conversation thread messages (role, content, timestamps) |

---

## 4. Data Flows

### 4.1 User → Telegram → HA
```
User (Telegram message)
  │
  ▼
OpenClaw Gateway (LXC)
  │ POST localhost:11434/api/chat  [tool calling enabled]
  ▼
Ollama / Qwen 2.5 14B
  │ returns: tool_call → ha_light_control(entity="light.salon", action="turn_on")
  ▼
OpenClaw ha-light Skill
  │ POST http://HAOS_IP:8123/api/services/light/turn_on
  │ Authorization: Bearer ${HA_TOKEN}
  ▼
Home Assistant Core
  │ executes action
  ▼
OpenClaw streams confirmation back to Telegram
```

### 4.2 Historical Query
```
User: "¿Cuál fue la temperatura media del salón ayer?"
  │
  ▼
OpenClaw ha-history Skill
  │ 1. Sends NL description to Qwen → Qwen generates Flux query
  │ 2. POST http://HAOS_IP:8086/api/v2/query
  │    Authorization: Token ${INFLUXDB_TOKEN}
  │    Body: Flux query string
  ▼
InfluxDB returns data points
  │
  ▼
Qwen formats result → Telegram response
```

### 4.3 Health Check
```
ha-sentinel daemon (every 60 s)
  ├── GET  http://LXC_IP:11434/api/tags          → Ollama + model status
  ├── GET  http://supervisor/core/info            → HA Supervisor latency
  ├── influxdb_client.ping()                      → InfluxDB connectivity
  └── telegram_bot.get_me()                       → Telegram auth

All → InfluxDB ha_sentinel_metrics [measurement: health_check]
Any failure → Telegram alert to admin_chat_id
```

### 4.4 Alexa
```
Alexa Skill (cloud)
  │ POST http://HAOS_IP:8099/alexa
  │ { "text": "enciende la luz del salón" }
  ▼
ha-sentinel alexa.py
  │ POST http://LXC_IP:11434/api/chat  (simple completion, no tools)
  ▼
Ollama / Qwen 2.5
  │ plain-text response
  ▼
{ "response": "Encendida la luz del salón.", "success": true }
```

---

## 5. Security Model

| Surface | Protection |
|---|---|
| Telegram | `allowed_chat_ids` whitelist in OpenClaw config; all other senders silently dropped |
| HA Token | Long-lived token stored in `~/.openclaw/` on LXC — **never in the git repo** |
| InfluxDB Token | Stored in `~/.openclaw/` on LXC and in HA Add-on options — **never in git** |
| Ollama | Bound to `127.0.0.1`; only accessible from within the LXC |
| Alexa endpoint | Binds to local network interface; optional Bearer token (Add-on options) |
| Secrets in repo | All template files use `{{PLACEHOLDER}}` — real values in deploy-time configs |

---

## 6. Failsafe Strategy

| Failure | Behaviour |
|---|---|
| Ollama timeout > 15 s | OpenClaw returns error to user; does NOT block event loop |
| HA service call fails | Log `{"event":"ha_call_failed","detail":"..."}`, report to user |
| InfluxDB unreachable | Log and skip write; health check alerts admin |
| Telegram unreachable | Health check alerts via InfluxDB annotation; OpenClaw queues retry |

---

## 7. Repository Structure

```
ha-sentinel-orchestrator/
│
├── ARCHITECTURE.md                   ← This document
├── README.md
├── .gitignore
│
├── ha-addon/                         ── HAOS Add-on (Python 3.12, minimal)
│   ├── config.yaml                   ← Add-on manifest + options schema
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── run.sh
│   └── src/
│       ├── main.py                   ← asyncio entrypoint
│       ├── config.py                 ← Load options.json
│       ├── observability/
│       │   └── health.py             ← Health check daemon (60 s)
│       ├── interfaces/
│       │   └── alexa.py              ← Alexa HTTP endpoint (:8099)
│       └── utils/
│           └── logging.py            ← Structured JSON logging
│
└── openclaw-config/                  ── OpenClaw deployment (AI LXC)
    ├── config.json5                  ← Config template (no real values)
    ├── deploy.sh                     ← Deploy script: copies to ~/.openclaw/
    └── workspace/
        ├── AGENTS.md                 ← Agent pool definitions
        ├── SOUL.md                   ← Agent personality (es-ES)
        └── skills/
            ├── ha-light/
            │   └── SKILL.md          ← Light on/off/brightness
            ├── ha-climate/
            │   └── SKILL.md          ← Thermostat / HVAC
            ├── ha-status/
            │   └── SKILL.md          ← Full home state snapshot
            ├── ha-history/
            │   └── SKILL.md          ← NL → Flux → InfluxDB query
            ├── ha-metrics/
            │   └── SKILL.md          ← Write TTFT/TPS to InfluxDB
            └── ha-memory/
                └── SKILL.md          ← Persist conversation threads
```

---

## 8. LXC Deployment Guide

### Proxmox: Create AI LXC

```bash
# In Proxmox shell — create privileged LXC (Debian 12, 4 cores, 8 GB RAM)
pct create 1XX local:vztmpl/debian-12-standard_12.x_amd64.tar.zst \
  --hostname ai-sentinel \
  --cores 4 \
  --memory 8192 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 0   # privileged — required for ROCm /dev/kfd

# Add GPU device passthrough to /etc/pve/lxc/1XX.conf:
echo 'lxc.cgroup2.devices.allow: c 226:129 rwm'   >> /etc/pve/lxc/1XX.conf
echo 'lxc.cgroup2.devices.allow: c 234:0 rwm'   >> /etc/pve/lxc/1XX.conf
echo 'lxc.mount.entry: /dev/dri/renderD129 dev/dri/renderD129 none bind,optional,create=dir' \
                                                  >> /etc/pve/lxc/1XX.conf
echo 'lxc.mount.entry: /dev/kfd dev/kfd none bind,optional,create=file' \
                                                  >> /etc/pve/lxc/1XX.conf
```

### Inside the AI LXC

```bash
# 1. ROCm 6.x
apt-get install -y rocm

# 2. Verify GPU visible
rocm-smi

# 3. Ollama with ROCm
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b
ollama pull qwen2.5:7b

# 4. OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash
# Follow onboard: choose Ollama provider, Local only mode

# 5. Deploy this repo's openclaw-config
git clone https://github.com/YOUR_ORG/ha-sentinel-orchestrator.git
cd ha-sentinel-orchestrator/openclaw-config
./deploy.sh   # copies workspace/ and config.json5 to ~/.openclaw/
              # prompts for real tokens (not stored in git)
```

### HA Add-on

```
1. Add repo URL to HA Add-on Store
2. Install "HA-Sentinel Orchestrator"
3. Fill options panel (LXC IP, InfluxDB token, Alexa secret)
4. Start add-on
```

---

## 9. Observability

All metrics flow to InfluxDB → visualised in Grafana (off-the-shelf panels).
Custom Python analytics are only added if a specific requirement cannot be
satisfied with Flux queries + Grafana.

| Metric | Source | InfluxDB field |
|---|---|---|
| TTFT | OpenClaw ha-metrics skill | `ttft_ms` |
| TPS | OpenClaw ha-metrics skill | `tps` |
| Token usage | OpenClaw ha-metrics skill | `prompt_tokens`, `completion_tokens` |
| Health latency | ha-sentinel health daemon | `latency_ms` |
| Service status | ha-sentinel health daemon | `status` (ok/degraded/error) |
