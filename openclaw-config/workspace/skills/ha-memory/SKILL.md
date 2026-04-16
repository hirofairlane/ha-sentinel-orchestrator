---
name: ha_memory
description: Persist conversation thread messages to InfluxDB for long-term memory
---

# HA Conversation Memory

Use this skill to save important conversation turns to InfluxDB so they can be
retrieved in future sessions.

## Write a conversation turn
```bash
# Escape the content string before embedding it
CONTENT_B64=$(echo -n "MESSAGE_CONTENT" | base64 -w 0)

curl -s -X POST "$INFLUXDB_URL/api/v2/write?org=$INFLUXDB_ORG&bucket=ha_sentinel_memory&precision=ms" \
  -H "Authorization: Token $INFLUXDB_TOKEN" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-binary "conversation,agent_id=sentinel,thread_id=THREAD_ID role=\"ROLE\",content_b64=\"$CONTENT_B64\" $(date +%s%3N)"
```

## When to save
- User preferences expressed explicitly ("prefiero las luces cálidas por la noche")
- Recurring schedules or routines mentioned by the user
- Important context about the home (rooms, device names, user habits)

## When NOT to save
- Routine commands (turning lights on/off) — these are ephemeral
- Error messages or debugging output
