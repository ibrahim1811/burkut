import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from server import ws
from server.auth import require_token
from server.routes import memory, system

PORT = 8765
DASHBOARD_DIST = Path(__file__).parent.parent / "dashboard" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Bürküt OS API", version="0.1.0")

    app.include_router(system.router, dependencies=[Depends(require_token)])
    app.include_router(memory.router, dependencies=[Depends(require_token)])
    app.include_router(ws.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    if DASHBOARD_DIST.exists():
        app.mount("/", StaticFiles(directory=str(DASHBOARD_DIST), html=True), name="dashboard")

    return app


def start_in_thread(port: int = PORT) -> threading.Thread:
    import uvicorn

    from memory import store
    store.get_conn()

    config = uvicorn.Config(create_app(), host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="burkut-server")
    thread.start()
    return thread


if __name__ == "__main__":
    import uvicorn

    from memory import store
    store.get_conn()
    uvicorn.run(create_app(), host="0.0.0.0", port=PORT)
