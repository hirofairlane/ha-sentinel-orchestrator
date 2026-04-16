---
name: ha_light_control
description: Control Home Assistant lights — turn on/off, set brightness and colour temperature
---

# HA Light Control

Use this skill when the user asks to turn a light on or off, change brightness,
or adjust colour temperature.

## How to execute

Use the `exec` tool to call the HA REST API. The env vars `$HA_URL` and `$HA_TOKEN`
are available in the shell environment.

### Turn on (basic)
```bash
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "ENTITY_ID"}'
```

### Turn on with brightness (0–100 %) and colour temperature (Kelvin)
```bash
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "ENTITY_ID", "brightness_pct": BRIGHTNESS, "color_temp_kelvin": KELVIN}'
```

### Turn off
```bash
curl -s -X POST "$HA_URL/api/services/light/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "ENTITY_ID"}'
```

## Entity ID format
`light.<room_name>` — e.g. `light.salon`, `light.dormitorio`, `light.cocina`.
If unsure of the entity ID, run `ha_status` first to list current entities.

## Success
HTTP 200 = action executed. Confirm to the user in one short sentence.
HTTP 4xx/5xx = report the status code and body as a technical error.
