---
name: srv_infra
description: Consultar estado y ejecutar operaciones en servidores de infraestructura (zeratul, plex, crafty, frigate, h340) via SSH
---

# Gestión de servidores de infraestructura

Usa este skill cuando el usuario pregunte por el estado de servidores, disco, memoria, procesos,
o quiera lanzar operaciones como backups, reinicios de servicios, etc.

IMPORTANTE: Usa siempre la ruta completa `/usr/bin/srv` para garantizar que funciona.

## Servidores disponibles

| Nombre   | IP              | Rol                        |
|----------|-----------------|----------------------------|
| zeratul  | 192.168.1.122   | Proxmox host principal     |
| plex     | 192.168.1.123   | NAS 18T, Plex, Jellyfin    |
| crafty   | 192.168.1.36    | Servidor Minecraft         |
| frigate  | 192.168.1.170   | NVR cámaras                |
| h340     | 192.168.1.129   | Proxmox failback           |

## Consultas rápidas de estado

### Estado general (uptime + RAM + disco raíz)
```bash
/usr/bin/srv zeratul status
```

### Estado de todos los servidores
```bash
/usr/bin/srv all status
```

### Espacio en disco detallado
```bash
/usr/bin/srv plex df
```

### Memoria RAM
```bash
/usr/bin/srv plex mem
```

### Temperatura CPU
```bash
/usr/bin/srv zeratul temp
```

### Procesos top CPU
```bash
/usr/bin/srv zeratul top5
```

### Actualizaciones pendientes
```bash
/usr/bin/srv zeratul updates
```

### Comando libre en cualquier servidor
```bash
/usr/bin/srv plex -- df -h /mnt/18T
```
```bash
/usr/bin/srv zeratul -- systemctl status ollama
```
```bash
/usr/bin/srv frigate -- journalctl -u frigate --since "1 hour ago" | tail -30
```

## Operaciones largas (backups, rsync, etc.)

Para operaciones que tardan minutos, usa este patrón:

### Paso 1 — Lanzar en background y obtener el PID
```bash
/usr/bin/srv plex -- "nohup tar czf /tmp/backup_$(date +%Y%m%d_%H%M%S).tar.gz /ruta/carpeta > /tmp/backup.log 2>&1 & echo PID:$!"
```

### Paso 2 — Comprobar estado (con el PID del paso 1)
```bash
/usr/bin/srv plex -- "kill -0 PID_AQUI 2>/dev/null && echo 'EN CURSO' || echo 'TERMINADO'; tail -5 /tmp/backup.log"
```

## Reglas para operaciones asíncronas

1. Antes de lanzar una operación larga, describe al usuario qué vas a hacer.
2. Lanza en background con `nohup ... & echo PID:$!` para obtener el PID.
3. Informa al usuario del PID y del fichero de log.
4. Para comprobar el estado cuando el usuario pregunte, usa el Paso 2 con el PID real.

## Notas

- Nunca uses `ssh` directamente — usa siempre `/usr/bin/srv`.
- Si un servidor no responde, informa del error exacto sin inventar el estado.
