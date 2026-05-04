---
name: ha_light_control
description: Control Home Assistant lights via REST API — turn on/off, brightness, colour temperature, RGB. (Para grupos persistentes ver ha_group_helper.)
---

# HA Light Control

Use this skill when the user asks to turn a light on or off, change brightness,
colour temperature, or RGB colour.

> **Para crear un grupo persistente de luces** (que aparezca como dispositivo único en HA), ver el skill `ha_group_helper`. Aquí solo se controla el estado.

## How to execute — IMPORTANT

These are **bash commands you must execute with `exec`**. They are NOT structured tool calls.
Do NOT emit `<tool_call>{...}</tool_call>` JSON — that does nothing in this system.

**JSON safety rule:** never inline JSON with nested quotes inside curl. Always write the payload to `/tmp/ha_payload.json` first, then `curl -d @/tmp/ha_payload.json`.

The env vars `$HA_URL` and `$HA_TOKEN` are available in the shell environment.

### Turn on (basic)
```bash
printf '%s' '{"entity_id": "ENTITY_ID"}' > /tmp/ha_payload.json
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/ha_payload.json
```

### Turn on with brightness (0–100 %) and colour temperature (Kelvin)
```bash
printf '%s' '{"entity_id": "ENTITY_ID", "brightness_pct": BRIGHTNESS, "color_temp_kelvin": KELVIN}' > /tmp/ha_payload.json
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/ha_payload.json
```

### Turn on with RGB colour
```bash
printf '%s' '{"entity_id": "ENTITY_ID", "rgb_color": [R, G, B]}' > /tmp/ha_payload.json
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/ha_payload.json
```

### Turn off
```bash
printf '%s' '{"entity_id": "ENTITY_ID"}' > /tmp/ha_payload.json
curl -s -X POST "$HA_URL/api/services/light/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/ha_payload.json
```

### Control multiple lights at once (no group needed)

Pass a list of entity IDs in one call. This is the right approach when the user
wants several lights to behave identically and doesn't need a persistent device:

```bash
printf '%s' '{"entity_id": ["light.luz_gaming_1", "light.luz_gaming_2"], "brightness_pct": 80}' > /tmp/ha_payload.json
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/ha_payload.json
```

## Verify after acting

After every state change, verify by reading the current state:
```bash
curl -s "$HA_URL/api/states/ENTITY_ID" \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('state'), d.get('attributes',{}).get('brightness'))"
```

## Entity ID format
`light.<name>` — e.g. `light.luz_gaming_1`, `light.salon`.
If unsure of the entity ID, look in `ENTITIES.md` first or run `ha_status`.

## Success / failure
- HTTP 200 = action sent. **Always verify the resulting state before telling the user "done"**.
- HTTP 4xx/5xx = report the status code and body as a technical error. Don't retry blindly.
