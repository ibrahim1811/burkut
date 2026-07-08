"""memory.json → data/burkut.db tek yönlü migrasyon. memory.json silinmez."""

import json
import time
from datetime import datetime
from pathlib import Path

from memory import store

MEMORY_JSON = Path(__file__).parent / "memory.json"


def _ts(iso: str | None) -> float:
    if not iso:
        return time.time()
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return time.time()


def migrate() -> None:
    if not MEMORY_JSON.exists():
        print("memory.json bulunamadı, migrasyon atlandı.")
        return

    data = json.loads(MEMORY_JSON.read_text(encoding="utf-8"))
    conn = store.get_conn()

    n_conv = n_msg = n_rem = n_learn = 0

    for conv in data.get("conversations", []):
        cid = str(conv.get("id", ""))
        if not cid:
            continue
        existing = store.read("SELECT 1 FROM conversations WHERE id=?", (cid,))
        if existing:
            continue
        store.write(
            "INSERT INTO conversations (id, channel, started_at, last_updated) VALUES (?, ?, ?, ?)",
            (cid, "telegram", _ts(conv.get("started")), _ts(conv.get("last_updated"))),
        )
        n_conv += 1
        for msg in conv.get("messages", []):
            store.write(
                "INSERT INTO messages (conversation_id, role, content, ts) VALUES (?, ?, ?, ?)",
                (cid, msg.get("role", "user"), msg.get("content", ""), _ts(msg.get("ts"))),
            )
            n_msg += 1

    for rem in data.get("reminders", []):
        rid = str(rem.get("id", ""))
        if not rid or store.read("SELECT 1 FROM reminders WHERE id=?", (rid,)):
            continue
        store.write(
            "INSERT INTO reminders (id, chat_id, text, when_iso, done, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rid, rem.get("chat_id"), rem.get("text", ""), rem.get("when", ""),
             int(bool(rem.get("done"))), time.time()),
        )
        n_rem += 1

    for item in data.get("learned", []):
        content = f"{item.get('title', '')}\n{item.get('summary', '')}"
        facts = item.get("facts") or []
        if facts:
            content += "\n" + "\n".join(f"- {f}" for f in facts)
        store.add_memory(
            content.strip(), kind="fact", source="migration", importance=0.6,
            metadata={"url": item.get("url", "")},
        )
        n_learn += 1

    for proj in data.get("projects", []):
        store.add_memory(
            f"Proje: {proj.get('name', '')} — {proj.get('description', '')} ({proj.get('path', '')})",
            kind="project", source="migration", importance=0.7,
        )

    conn.commit()
    print(f"Migrasyon tamam: {n_conv} konuşma, {n_msg} mesaj, {n_rem} hatırlatıcı, {n_learn} öğrenilen kaynak.")
    print(f"DB: {store.DB_PATH}")
    print("memory.json korundu (dual-write dönemi bitince read-only yapılacak).")


if __name__ == "__main__":
    migrate()
