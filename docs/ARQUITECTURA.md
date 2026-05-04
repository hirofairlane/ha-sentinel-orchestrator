# Jarvis — Documentación Técnica

> Sistema de IA local para Home Assistant. Última actualización: 2026-04-18.

---

## Arquitectura general

```
[Telegram] ──► OpenClaw (Node.js, LXC 104) ──► ha CLI ──► Home Assistant REST API
                      │
                      └──► Ollama (ROCm gfx1200, localhost:11434)
                                 └── jarvis:14b (Qwen2.5 14B Q4_K_M, ~30 tok/s)
```

---

## Infraestructura

| Componente | Detalle |
|---|---|
| Proxmox host "Zeratul" | 192.168.1.122 · i5-14400 · 64GB DDR5 5200 MT/s XMP |
| AI LXC | ID 104 · IP 192.168.1.70 · privileged · Ubuntu |
| NAS | 192.168.1.123 · `//192.168.1.123/18t/MIO/Proyectos/IA_local` |
| Proxmox kernel | **6.14.11-6-bpo12-pve** (requerido para ROCm gfx1200) |
| CPU governor | `performance` (4100 MHz, en host Proxmox) |

---

## GPU — RDNA4 (gfx1200)

| Parámetro | Valor |
|---|---|
| PCI ID | 1002:7590 rev c0 |
| PCI slot | 0000:03:00.0 |
| Arquitectura | gfx1200 (RDNA4) — **NO es RX 7900 GRE** |
| Compute Units | 32 |
| VRAM | 15.9 GiB |
| Max clock | 2780 MHz |
| ROCm backend | nativo gfx1200 (sin HSA_OVERRIDE) |
| Rendimiento | ~30 tok/s con Qwen2.5 14B Q4_K_M |

### ADVERTENCIA: HSA_OVERRIDE_GFX_VERSION

`HSA_OVERRIDE_GFX_VERSION=11.0.0` **NO debe usarse** con esta GPU.
Causa GPU MODE1 reset (sq_intr shader errors) porque los kernels gfx1100 son incompatibles con gfx1200.

### Passthrough LXC 104 (`/etc/pve/lxc/104.conf`)

```
dev0: /dev/dri/renderD128,gid=993   # Intel iGPU render
dev1: /dev/dri/renderD129,gid=993   # AMD GPU render (ROCm)
dev2: /dev/dri/card1,gid=44         # Intel iGPU display  (era card0 antes de XMP)
dev3: /dev/dri/card2,gid=44         # AMD GPU display     (era card1 antes de XMP)
dev4: /dev/kfd,gid=993              # ROCm KFD (234:0)
```

> Al habilitar XMP en BIOS, los cards DRI se renumeran. Verificar con
> `ls -la /dev/dri/by-path/` en el host si el LXC no arranca con error "card0 does not exist".

### Kernel requerido

El SMU firmware de esta GPU es `if=0x32`. Requiere driver `if≥0x2e`:

| Kernel Proxmox | SMU driver if | ROCm gfx1200 |
|---|---|---|
| 6.11 | 0x26 | **NO** — GPU reset en compute |
| **6.14** | **0x2e** | **SÍ** — funciona |

```bash
# Instalar kernel 6.14
apt-get install proxmox-kernel-6.14.11-6-bpo12-pve
proxmox-boot-tool kernel pin 6.14.11-6-bpo12-pve
reboot
```

---

## Ollama

| Parámetro | Valor |
|---|---|
| Binario | `/usr/bin/ollama` (instalado vía install.sh) |
| Versión | 0.21.0 |
| Librerías ROCm | `/usr/lib/ollama/rocm/` |
| Modelos | `/usr/share/ollama/.ollama/models/` |
| Endpoint | `http://localhost:11434` (NO añadir /v1 — rompe tool calling) |

### `/etc/systemd/system/ollama.service.d/performance.conf`

```ini
[Service]
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_LOAD_TIMEOUT=10m"
Nice=-10
```

### Modelfile jarvis:14b (`/root/Modelfile.jarvis`)

```
FROM qwen2.5:14b
PARAMETER num_ctx 20480
PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>
PARAMETER temperature 0.3
```

```bash
# Recrear el modelo personalizado:
pct exec 104 -- bash -c "ollama create jarvis:14b -f /root/Modelfile.jarvis"
```

### Métricas de inferencia (GPU)

```
offloaded 49/49 layers to GPU
ROCm0 model buffer size  = 8148 MiB
ROCm0 KV buffer size     = 3840 MiB
ROCm0 compute buffer     =  367 MiB
Velocidad                = ~30 tok/s
```

---

## OpenClaw

| Parámetro | Valor |
|---|---|
| Config | `/root/.openclaw/openclaw.json` |
| Secrets | `/root/.openclaw/.env` (NO en git) |
| Workspace | `/root/.openclaw/workspace/` (auto-cargado en system prompt) |

### Campos clave en openclaw.json

```json
{
  "agents": {
    "defaults": {
      "model": "ollama/jarvis:14b",
      "contextTokens": 20480,
      "verboseDefault": "off"
    }
  },
  "api": { "provider": "ollama", "baseUrl": "http://localhost:11434" },
  "channels": {
    "telegram": { "streaming": { "mode": "off" } }
  }
}
```

---

## `ha` CLI — `/usr/local/bin/ha`

Wrapper Python para la REST API de Home Assistant.
Todos los POST usan `capture_output=True` para evitar flooding de JSON (WLED: 8000+ tokens).

| Comando | Descripción |
|---|---|
| `ha lights` | Estado de todas las luces |
| `ha search TERMINO` | Buscar entity_id por nombre amigable |
| `ha on ENTITY [params]` | Encender (soporta brightness_pct, color_temp_kelvin) |
| `ha off ENTITY` | Apagar |
| `ha state ENTITY` | Estado de una entidad |
| `ha states DOMINIO` | Todas las entidades de un dominio |
| `ha history ENTITY [horas]` | Historial últimas N horas (max 20 entradas) |
| `ha call DOM.SERVICIO ENTITY` | Llamar cualquier servicio HA |
| `ha cameras` | Listar cámaras disponibles |
| `ha photo [ENTITY]` | Enviar foto(s) por Telegram |

Variables de entorno requeridas en `/root/.openclaw/.env`:
```
HA_URL=http://...
HA_TOKEN=...
TG_TOKEN=...
TG_CHAT_ID=...
INFLUXDB_URL=...
INFLUXDB_TOKEN=...
INFLUXDB_ORG=...
```

---

## Cache de entidades — ENTITIES.md

| Parámetro | Valor |
|---|---|
| Archivo | `/root/.openclaw/workspace/ENTITIES.md` |
| Script | `/usr/local/bin/ha-refresh-entities` |
| Cron | `/etc/cron.d/ha-jarvis` (cada 8h) |
| Entidades | ~208 activas |
| Tokens | ~3600 tokens |

Filtros aplicados:
- Excluye estados: `unavailable`, `unknown`, `disabled`, `hidden`
- Excluye sufijos técnicos: `_bird`, `_cat`, `_do_not_disturb`, `_segment_N`, ebusd, etc.
- Solo incluye entidades con friendly_name diferente al slug

---

## SOUL.md — System prompt de Jarvis

| Ubicación | Ruta |
|---|---|
| LXC (activo) | `/root/.openclaw/workspace/SOUL.md` |
| NAS (copia) | `openclaw-config/workspace/SOUL.md` |

**Regla absoluta:** Jarvis llama a `exec` ANTES de escribir cualquier texto.
Flujo obligatorio: `exec → resultado → respuesta corta`.

---

## Diagnóstico rápido

```bash
# Verificar GPU activa
pct exec 104 -- journalctl -u ollama --no-pager -n 3 | grep "inference compute"
# Resultado esperado: library=ROCm compute=gfx1200 total="15.9 GiB"

# Test de velocidad de inferencia
pct exec 104 -- bash -c 'curl -s -X POST http://127.0.0.1:11434/api/generate \
  -d "{\"model\":\"jarvis:14b\",\"prompt\":\"hola\",\"stream\":false}" \
  | grep eval_duration'

# LXC no arranca (card no existe)
ls -la /dev/dri/by-path/     # en el host Proxmox
# Ver qué card* es AMD y actualizar /etc/pve/lxc/104.conf

# GPU reset en compute
dmesg | grep "MODE1 reset"
# Solución: actualizar kernel a 6.14+ (proxmox-kernel-6.14.11-6-bpo12-pve)

# Reinstalar Ollama (conserva modelos en /usr/share/ollama/)
curl -fsSL https://ollama.com/install.sh | sh
# Restaurar performance.conf y reiniciar servicio
```
