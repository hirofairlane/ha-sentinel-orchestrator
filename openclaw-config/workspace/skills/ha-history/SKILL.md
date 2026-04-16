---
name: ha_history
description: Query historical sensor data from InfluxDB using natural language
---

# HA Historical Data Query

Use this skill when the user asks about past sensor readings, trends, averages,
or any time-series data (temperature history, energy consumption, motion events, etc.).

## Process

1. **Understand the request** — identify the entity, time range, and aggregation needed.
2. **Write a Flux query** for InfluxDB based on the description.
3. **Execute the query** against InfluxDB.
4. **Summarise the results** in natural language for the user.

## Execute a Flux query
```bash
curl -s -X POST "$INFLUXDB_URL/api/v2/query?org=$INFLUXDB_ORG" \
  -H "Authorization: Token $INFLUXDB_TOKEN" \
  -H "Content-Type: application/vnd.flux" \
  -H "Accept: application/csv" \
  --data-binary 'FLUX_QUERY_HERE'
```

## Flux query template
```flux
from(bucket: "homeassistant")
  |> range(start: -24h)
  |> filter(fn: (r) => r["entity_id"] == "sensor.temperatura_salon")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

## Common patterns
- Last 24 h mean: `range(start: -24h)` + `aggregateWindow(every: 1h, fn: mean)`
- Yesterday: `range(start: -48h, stop: -24h)`
- Last week: `range(start: -7d)` + `aggregateWindow(every: 1d, fn: mean)`
- Max value: replace `fn: mean` with `fn: max`

## Output
Describe the results conversationally. Include min/max/avg if relevant.
If no data is found, say so clearly and suggest checking the entity ID.
