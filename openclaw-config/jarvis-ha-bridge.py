#!/usr/bin/env python3
import os, re, subprocess, time, uuid
from pathlib import Path
import httpx, uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
OLLAMA_URL = "http://localhost:11434"
MODEL = "jarvis:14b"
WORKSPACE = Path("/root/.openclaw/workspace")
ENV_FILE = Path("/root/.openclaw/.env")

def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

def load_system_prompt():
    soul = (WORKSPACE / "SOUL.md").read_text()
    entities_path = WORKSPACE / "ENTITIES.md"
    if entities_path.exists():
        soul += "\n\n# Entidades HA disponibles\n" + entities_path.read_text()[:6000]
    return soul

def run_command(cmd, env):
    full_env = {**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin", **env}
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, env=full_env)
        return (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"

def extract_exec_blocks(text):
    pattern = r"```(?:bash|shell|exec|)?\n(.*?)\n```"
    blocks = re.findall(pattern, text, re.DOTALL)
    safe = []
    for block in blocks:
        block = block.strip()
        first = block.split("\n")[0]
        if any(first.startswith(p) for p in ["ha ", "python3 ", "curl "]):
            safe.append(block)
    return safe

async def ollama_chat(messages):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OLLAMA_URL}/api/chat", json={
            "model": MODEL, "messages": messages, "stream": False,
            "options": {"num_ctx": 20480, "temperature": 0.3},
        })
        return r.json()["message"]["content"]

async def run_with_tools(messages, env):
    response = await ollama_chat(messages)
    blocks = extract_exec_blocks(response)
    if not blocks:
        return response
    results = [f"$ {cmd}\n{run_command(cmd, env)}" for cmd in blocks]
    messages2 = messages + [
        {"role": "assistant", "content": response},
        {"role": "user", "content": "Resultado:\n" + "\n".join(results) + "\n\nResponde al usuario con el resultado."},
    ]
    return await ollama_chat(messages2)

async def process(messages):
    env = load_env()
    sp = load_system_prompt()
    if not any(m["role"] == "system" for m in messages):
        messages = [{"role": "system", "content": sp}] + messages
    return await run_with_tools(messages, env)

@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    body = await request.json()
    content = await process(body.get("messages", []))
    return JSONResponse({"id": "chatcmpl-" + uuid.uuid4().hex[:8], "object": "chat.completion",
        "created": int(time.time()), "model": MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})

@app.get("/v1/models")
async def openai_models():
    return JSONResponse({"object": "list", "data": [{"id": MODEL, "object": "model",
        "created": int(time.time()), "owned_by": "jarvis"}]})

@app.get("/api/tags")
async def ollama_tags():
    return JSONResponse({"models": [{"name": MODEL, "model": MODEL,
        "modified_at": "2026-04-21T00:00:00Z", "size": 9000000000,
        "details": {"family": "qwen3"}}]})

@app.post("/api/chat")
async def ollama_chat_ep(request: Request):
    body = await request.json()
    content = await process(body.get("messages", []))
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return JSONResponse({"model": MODEL, "created_at": ts,
        "message": {"role": "assistant", "content": content},
        "done": True, "done_reason": "stop"})

@app.post("/api/generate")
async def ollama_generate(request: Request):
    body = await request.json()
    content = await process([{"role": "user", "content": body.get("prompt", "")}])
    return JSONResponse({"model": MODEL, "response": content, "done": True})

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=11435, log_level="info")
