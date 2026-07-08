from fastapi import APIRouter
from pydantic import BaseModel

from memory import store
from memory.search import search as mem_search

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryIn(BaseModel):
    content: str
    kind: str = "note"
    importance: float = 0.5


@router.get("/search")
def search(q: str, top_k: int = 5) -> list[dict]:
    return mem_search(q, top_k=top_k)


@router.get("/recent")
def recent(n: int = 20) -> list[dict]:
    rows = store.read(
        "SELECT id, kind, content, source, importance, created_at "
        "FROM memories ORDER BY created_at DESC LIMIT ?", (n,))
    return [dict(r) for r in rows]


@router.post("")
def add(item: MemoryIn) -> dict:
    mid = store.add_memory(item.content, kind=item.kind,
                           source="dashboard", importance=item.importance)
    return {"id": mid}


@router.delete("/{memory_id}")
def delete(memory_id: int) -> dict:
    store.write("DELETE FROM memories WHERE id=?", (memory_id,))
    return {"deleted": memory_id}
