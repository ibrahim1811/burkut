import math
import time

import numpy as np

from memory import embedder, store

RECENCY_HALF_LIFE_DAYS = 30.0


def _backfill_embeddings(limit: int = 64) -> None:
    rows = store.read(
        "SELECT id, content FROM memories WHERE embedding IS NULL LIMIT ?", (limit,))
    if not rows:
        return
    vecs = embedder.embed([r["content"] for r in rows])
    if vecs is None:
        return
    for row, vec in zip(rows, vecs):
        store.write("UPDATE memories SET embedding=? WHERE id=?",
                    (vec.astype(np.float32).tobytes(), row["id"]))


def _rank_score(similarity: float, created_at: float, importance: float) -> float:
    age_days = max(0.0, (time.time() - created_at) / 86400)
    recency = math.exp(-math.log(2) * age_days / RECENCY_HALF_LIFE_DAYS)
    return similarity * (0.5 + 0.5 * recency) * (0.5 + importance)


def search(query: str, top_k: int = 5) -> list[dict]:
    """Hybrid arama: FTS5 BM25 + vektör kosinüs (varsa), RRF birleşimi."""
    scores: dict[int, float] = {}

    fts_q = " OR ".join(w for w in query.split() if len(w) > 1) or query
    try:
        fts = store.read(
            "SELECT rowid, rank FROM memories_fts WHERE memories_fts MATCH ? "
            "ORDER BY rank LIMIT 20", (fts_q,))
    except Exception:
        fts = []
    for i, row in enumerate(fts):
        scores[row["rowid"]] = scores.get(row["rowid"], 0) + 1.0 / (10 + i)

    qvec = embedder.embed([query])
    if qvec is not None:
        _backfill_embeddings()
        rows = store.read("SELECT id, embedding FROM memories WHERE embedding IS NOT NULL")
        if rows:
            mat = np.frombuffer(b"".join(r["embedding"] for r in rows),
                                dtype=np.float32).reshape(len(rows), -1)
            sims = mat @ qvec[0]
            for idx in np.argsort(-sims)[:20]:
                if sims[idx] > 0.25:
                    mid = rows[int(idx)]["id"]
                    scores[mid] = scores.get(mid, 0) + 1.0 / (10 + int(np.sum(sims > sims[idx])))

    if not scores:
        return []

    ids = list(scores)
    ph = ",".join("?" * len(ids))
    memrows = {r["id"]: r for r in store.read(
        f"SELECT id, kind, content, source, importance, created_at FROM memories WHERE id IN ({ph})", tuple(ids))}

    results = []
    for mid, s in scores.items():
        r = memrows.get(mid)
        if r:
            results.append({
                "id": mid, "kind": r["kind"], "content": r["content"],
                "source": r["source"],
                "score": _rank_score(s, r["created_at"], r["importance"]),
            })
    results.sort(key=lambda x: -x["score"])
    top = results[:top_k]
    if top:
        ph = ",".join("?" * len(top))
        store.write(
            f"UPDATE memories SET access_count=access_count+1, last_accessed=? WHERE id IN ({ph})",
            (time.time(), *[t["id"] for t in top]))
    return top


if __name__ == "__main__":
    import sys
    for r in search(" ".join(sys.argv[1:]) or "test"):
        print(f"[{r['score']:.3f}] ({r['kind']}) {r['content'][:80]}")
