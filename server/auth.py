import os

from fastapi import HTTPException, Security, WebSocket
from fastapi.security.api_key import APIKeyHeader

_header = APIKeyHeader(name="X-Burkut-Token", auto_error=False)


def get_token() -> str:
    return os.environ.get("BURKUT_TOKEN") or os.environ.get("AGENT_TOKEN", "")


async def require_token(token: str | None = Security(_header)) -> None:
    if not token or token != get_token():
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik X-Burkut-Token")


def ws_auth(ws: WebSocket) -> bool:
    token = ws.query_params.get("token") or ws.headers.get("x-burkut-token")
    return bool(token) and token == get_token()
