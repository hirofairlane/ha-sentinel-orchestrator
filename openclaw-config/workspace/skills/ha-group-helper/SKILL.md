---
name: ha_group_helper
description: Crear grupos de luces persistentes en Home Assistant (vía YAML helper) o controlar varias luces juntas sin grupo persistente.
---

# HA Group Helper

Use this skill cuando el usuario quiera **agrupar varias luces como un dispositivo único** en Home Assistant.

## Important — read first

Hay **dos formas** de "agrupar luces". Elige la correcta según lo que pida el usuario:

### A) Control conjunto (sin grupo persistente) — recomendado para uso puntual

Si el usuario solo quiere encender/apagar/regular varias luces a la vez y no necesita verlas como un dispositivo único en HA UI, usa el skill `ha_light_control` con una lista de `entity_id`. No requiere crear nada en HA.

### B) Grupo persistente (Light Group helper)

Si el usuario quiere que aparezca **un dispositivo único en HA UI** ("Luz Gaming") que englobe a las dos:

> **No es posible crear este grupo de forma 100% automática vía REST API** sin pasar por un config flow interactivo. Las opciones reales son:

#### Opción 1 — UI manual (la más sencilla)

Decirle al usuario textualmente:

> "Para crear un dispositivo único 'Luz Gaming' en HA: ve a **Ajustes → Dispositivos y servicios → Ayudantes → + Crear ayudante → Grupo → Grupo de luces**. Nombre: Luz Gaming. Selecciona `light.luz_gaming_1` y `light.luz_gaming_2`. Tipo: 'all' o 'min/max' según prefieras. Mientras tanto te las controlo juntas."

#### Opción 2 — YAML en configuration.yaml (requiere reinicio de HA)

```bash
ssh root@192.168.1.131 'cat >> /config/configuration.yaml <<EOF

light:
  - platform: group
    name: "Luz Gaming"
    entities:
      - light.luz_gaming_1
      - light.luz_gaming_2
EOF'
```

Después llamar al servicio `homeassistant.reload_core_config` o reiniciar HA. **Avisar al usuario** que va a perder ~30 s la conexión con HA.

## Verify after acting

Tras crear el grupo (vía YAML + reload), comprobar que existe:
```bash
curl -s "$HA_URL/api/states/light.luz_gaming" -H "Authorization: Bearer $HA_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('state') else 'NO EXISTE')"
```

Si no existe: reportar al usuario, **no afirmar que se creó**.

## Anti-patrón — qué NUNCA hacer

❌ Emitir `<tool_call>{"name":"ha_light_control","arguments":{"action":"create_group",...}}</tool_call>`. Eso no existe. No se ejecuta nada.

❌ Decirle al usuario "se ha creado el grupo X" sin haber verificado con `curl /api/states/`.

❌ Repetir el mismo intento si la primera vez no apareció el grupo. Cambiar de enfoque o admitir la limitación.
