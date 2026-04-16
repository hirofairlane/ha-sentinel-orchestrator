---
name: ha_status
description: Get a full snapshot of all Home Assistant entity states
---

# HA Home Status

Use this skill when the user asks "¿qué está encendido?", "¿cómo está la casa?",
or when you need to find entity IDs before performing an action.

## Fetch all states
```bash
curl -s "$HA_URL/api/states" \
  -H "Authorization: Bearer $HA_TOKEN" | \
  python3 -c "
import json, sys
states = json.load(sys.stdin)
for s in states:
    print(s['entity_id'], '|', s['state'], '|', json.dumps(s.get('attributes', {})))
"
```

## Fetch a single entity
```bash
curl -s "$HA_URL/api/states/ENTITY_ID" \
  -H "Authorization: Bearer $HA_TOKEN"
```

## Output
Summarise the relevant entities in a human-readable list in Spanish.
Group by domain (lights, climate, sensors, switches).
Highlight any entities in unexpected states (e.g. lights on when nobody is home).
