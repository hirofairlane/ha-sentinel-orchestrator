---
name: ha_metrics
description: Write inference performance metrics (TTFT, TPS, token usage) to InfluxDB
---

# HA Metrics Writer

Use this skill automatically after every Ollama inference to record performance data.
Do not describe this process to the user unless they ask.

## Write a metric point
```bash
curl -s -X POST "$INFLUXDB_URL/api/v2/write?org=$INFLUXDB_ORG&bucket=ha_sentinel_metrics&precision=ms" \
  -H "Authorization: Token $INFLUXDB_TOKEN" \
  -H "Content-Type: text/plain; charset=utf-8" \
  --data-binary "inference,agent=sentinel,model=qwen2.5:14b ttft_ms=TTFT,tps=TPS,prompt_tokens=PT,completion_tokens=CT $(date +%s%3N)"
```

## Fields to populate
- `TTFT`: time-to-first-token in milliseconds (from Ollama response `prompt_eval_duration` / 1e6)
- `TPS`: tokens per second (`eval_count` / (`eval_duration` / 1e9))
- `PT`: prompt token count (`prompt_eval_count`)
- `CT`: completion token count (`eval_count`)

These values are available in the Ollama `/api/chat` response JSON when `stream: false`.
