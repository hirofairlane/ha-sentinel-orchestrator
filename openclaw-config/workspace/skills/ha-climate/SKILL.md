---
name: ha_climate_control
description: Control Home Assistant climate entities — set temperature, HVAC mode or preset
---

# HA Climate Control

Use this skill when the user asks to change room temperature, turn heating/cooling
on or off, or switch to a preset (eco, away, boost, etc.).

## Set target temperature
```bash
curl -s -X POST "$HA_URL/api/services/climate/set_temperature" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "ENTITY_ID", "temperature": TARGET_CELSIUS}'
```

## Set HVAC mode (heat | cool | auto | off | fan_only | dry)
```bash
curl -s -X POST "$HA_URL/api/services/climate/set_hvac_mode" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "ENTITY_ID", "hvac_mode": "MODE"}'
```

## Set preset mode (away | eco | boost | comfort | sleep)
```bash
curl -s -X POST "$HA_URL/api/services/climate/set_preset_mode" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "ENTITY_ID", "preset_mode": "PRESET"}'
```

## Entity ID format
`climate.<room_name>` — e.g. `climate.salon`, `climate.dormitorio`.

## Safety rule
If the user asks to turn off heating at night when the outside temperature is below 5 °C,
ask for confirmation before executing.
