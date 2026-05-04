#!/usr/bin/env python3
"""
Jarvis Sentinel v2 - corre en plex (LXC 101).
Comprobaciones:
  1. Gateway health  - /health via SSH a LXC 104
  2. Ollama tags     - /api/tags directo
  3. Zombie-gateway  - payloads=0 en journal de openclaw
Recuperacion escalonada: nivel1=openclaw, nivel2=ollama+openclaw.
"""
import time, subprocess, urllib.request, json
from pathlib import Path
from datetime import datetime

GATEWAY_URL  = "http://127.0.0.1:18789/health"
OLLAMA_TAGS  = "http://192.168.1.70:11434/api/tags"
OLLAMA_MODEL = "jarvis:14b"
LXC104_IP    = "192.168.1.70"
SSH_KEY      = "/root/.ssh/id_sentinel"
SSH_OPTS     = ["-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8"]

CHECK_EVERY      = 60
FAIL_THRESH      = 3
ZOMBIE_THRESH    = 4
TIMEOUT          = 12
RESTART_COOLDOWN = 300

ENV_FILE = Path("/root/.jarvis-sentinel.env")
LOG_FILE = Path("/var/log/jarvis-sentinel.log")
TG_BOT_TOKEN = None
TG_CHAT_ID   = None


def load_env():
    global TG_BOT_TOKEN, TG_CHAT_ID
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("TG_BOT_TOKEN="):
                TG_BOT_TOKEN = line.split("=", 1)[1].strip()
            elif line.startswith("TG_CHAT_ID="):
                TG_CHAT_ID = line.split("=", 1)[1].strip()


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[" + ts + "] " + msg
    print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def send_telegram(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    payload = json.dumps({"chat_id": TG_CHAT_ID, "text": msg}).encode()
    try:
        req = urllib.request.Request(
            "https://api.telegram.org/bot" + TG_BOT_TOKEN + "/sendMessage",
            data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log("[warn] Telegram: " + str(e))


def ssh_run(cmd, timeout=20):
    result = subprocess.run(
        ["ssh"] + SSH_OPTS + ["root@" + LXC104_IP, cmd],
        capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout.strip()


def check_gateway():
    try:
        rc, out = ssh_run("curl -sf --max-time " + str(TIMEOUT) + " " + GATEWAY_URL, timeout=TIMEOUT+10)
        if rc != 0:
            return False
        return json.loads(out).get("ok") is True
    except Exception:
        return False


def check_ollama():
    try:
        r = urllib.request.urlopen(OLLAMA_TAGS, timeout=TIMEOUT)
        data = json.loads(r.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        return any(OLLAMA_MODEL in m for m in models)
    except Exception:
        return False


def check_zombie_gateway():
    try:
        rc, out = ssh_run(
            "journalctl -u openclaw --no-pager --since '5 minutes ago' -o cat 2>/dev/null | grep -c payloads=0 || echo 0",
            timeout=15)
        count = int(out.strip() or "0")
        if count >= ZOMBIE_THRESH:
            log("[warn] Zombie-gateway: payloads=0 x" + str(count) + " en 5 min")
            return True
        return False
    except Exception:
        return False


def restart_jarvis(level=1):
    log("Reiniciando Jarvis nivel " + str(level) + "...")
    ok_marker = chr(34) + "ok" + chr(34) + ":true"
    if level >= 2:
        rc, out = ssh_run(
            "systemctl restart ollama; sleep 12; systemctl restart openclaw; sleep 8; curl -s http://127.0.0.1:18789/health",
            timeout=120)
    else:
        rc, out = ssh_run(
            "systemctl restart openclaw; sleep 8; curl -s http://127.0.0.1:18789/health",
            timeout=60)
    log("restart n=" + str(level) + " rc=" + str(rc) + " out=" + out[:80])
    if rc == 0 and ok_marker in out:
        return True
    if level < 2:
        log("Nivel 1 insuficiente, escalando...")
        return restart_jarvis(level=2)
    return False


def main():
    load_env()
    log("Jarvis Sentinel v2 arrancado")
    send_telegram("Jarvis Sentinel v2 activo en plex")

    gw_fails     = 0
    inf_fails    = 0
    last_restart = 0.0

    while True:
        try:
            gw_ok  = check_gateway()
            ol_ok  = check_ollama()
            zombie = check_zombie_gateway() if gw_ok and ol_ok else False
            all_ok = gw_ok and ol_ok and not zombie

            if all_ok:
                if gw_fails > 0 or inf_fails > 0:
                    log("Jarvis completamente operativo")
                    send_telegram("Jarvis recuperado - gateway y Ollama OK")
                gw_fails  = 0
                inf_fails = 0
            else:
                if not gw_ok:
                    gw_fails += 1
                    log("[warn] Gateway caido (" + str(gw_fails) + "/" + str(FAIL_THRESH) + ")")
                if not ol_ok:
                    inf_fails += 1
                    log("[warn] Ollama caido (" + str(inf_fails) + "/" + str(FAIL_THRESH) + ")")
                if zombie:
                    log("[warn] Zombie-gateway detectado")

            level        = 2 if not ol_ok else 1
            needs_action = zombie or max(gw_fails, inf_fails) >= FAIL_THRESH

            if needs_action:
                now = time.time()
                if now - last_restart > RESTART_COOLDOWN:
                    cause = "zombie-gateway" if zombie else ("gateway=KO" if not gw_ok else "ollama=KO")
                    log("Iniciando reinicio (" + cause + ")")
                    send_telegram("Jarvis no responde (" + cause + "). Reiniciando...")
                    ok = restart_jarvis(level=level)
                    last_restart = now
                    gw_fails  = 0
                    inf_fails = 0
                    if ok:
                        send_telegram("Jarvis reiniciado por el Sentinel")
                    else:
                        send_telegram("Jarvis no pudo reiniciarse. Intervencion manual necesaria.")
                else:
                    log("Fallo detectado pero cooldown activo")

        except Exception as e:
            log("[error] loop: " + str(e))

        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    main()