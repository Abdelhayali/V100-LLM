"""OpenAI-compatible API for whatever model is loaded on the PC, reachable through the tunnel from anywhere.

  base URL:  <tunnel URL>/openai/v1        (also http://127.0.0.1:<port>/openai/v1 on the PC itself)
  API key:   generated and refreshed from the phone app (separate from the app's pairing token)

Requests are forwarded unchanged to llm_base_url (the V100-LLM launcher's model on 8899), so the same URL and key keep
working when another model is loaded. The "model" field can be anything: llama.cpp serves the loaded model.
"""
import secrets
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from .app import _failures, client_ip, list_models, llm_headers, state
from .config import config, llm_api_base

router = APIRouter()        # public: protected by the API key, not by the app token
manage = APIRouter()        # app-only (mounted with the app token): show / refresh / turn off the key

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}
HOP = {"content-length", "transfer-encoding", "connection", "keep-alive", "content-encoding"}


def _err(status: int, msg: str, kind: str = "invalid_request_error") -> JSONResponse:
    return JSONResponse({"error": {"message": msg, "type": kind}}, status_code=status, headers=CORS)


def _check_key(req: Request) -> JSONResponse | None:
    key = config.data.get("openai_key") or ""
    if not key:
        return _err(403, "The OpenAI API is turned off. Generate a key in the phone app (menu -> API).", "permission_error")
    ip, now = client_ip(req), time.time()
    q = _failures[ip]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= 10:
        return _err(429, "Too many failed attempts, try again later", "rate_limit_error")
    auth = req.headers.get("authorization", "")
    given = auth[7:].strip() if auth.lower().startswith("bearer ") else req.headers.get("x-api-key", "")
    if not given or not secrets.compare_digest(given.encode(), key.encode()):
        q.append(now)
        return _err(401, "Invalid API key", "authentication_error")
    return None


@router.options("/openai/v1/{path:path}")
async def preflight(path: str):
    return Response(status_code=204, headers=CORS)


@router.api_route("/openai/v1/{path:path}", methods=["GET", "POST"])
async def proxy(path: str, req: Request):
    bad = _check_key(req)
    if bad:
        return bad
    url = llm_api_base() + "/" + path.lstrip("/")
    if req.url.query:
        url += "?" + req.url.query
    headers = {"Content-Type": req.headers.get("content-type", "application/json"), "Accept": req.headers.get("accept", "*/*"),
               **llm_headers()}
    client = httpx.AsyncClient(timeout=httpx.Timeout(1800, connect=10))
    try:
        r = await client.send(client.build_request(req.method, url, content=await req.body(), headers=headers), stream=True)
    except httpx.HTTPError:
        await client.aclose()
        return _err(503, "No model is running on the PC right now. Load one from the phone app (menu -> Models).",
                    "server_error")

    async def close():
        await r.aclose()
        await client.aclose()

    out = {k: v for k, v in r.headers.items() if k.lower() not in HOP} | CORS
    return StreamingResponse(r.aiter_raw(), status_code=r.status_code, headers=out,
                             media_type=r.headers.get("content-type"), background=BackgroundTask(close))


def _info() -> dict:
    key = config.data.get("openai_key") or ""
    pub = (state.get("public_url") or config.data.get("public_url") or "").rstrip("/")
    return {"enabled": bool(key), "key": key,
            "base_url": f"{pub}/openai/v1" if pub else "",
            "local_url": f"http://127.0.0.1:{config['port']}/openai/v1",
            "tunnel": bool(pub), "fixed_url": config.data.get("tunnel_mode") == "named"}


@manage.get("/api/openai")
async def info():
    d = _info()
    try:
        d["models"] = await list_models()
    except Exception:
        d["models"] = []
    return d


@manage.post("/api/openai/regenerate")
async def regenerate():
    """New key; the old one stops working at once."""
    config["openai_key"] = "sk-v100-" + secrets.token_urlsafe(32)
    return await info()


@manage.post("/api/openai/disable")
async def disable():
    config["openai_key"] = ""
    return await info()
