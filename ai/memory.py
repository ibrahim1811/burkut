"""
BÜRKÜT Hafıza Sistemi — memory.json üzerinden konuşma ve proje geçmişi yönetimi.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

MEMORY_FILE = Path(__file__).parent.parent / "memory.json"

_DEFAULTS = {
    "conversations": [],
    "projects": [],
    "files": {},
    "reminders": [],
}


def _load() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            # Bozuk dosyayı yedekle, veri kaybını önle
            backup = MEMORY_FILE.with_suffix(".bak")
            try:
                MEMORY_FILE.replace(backup)  # replace() overwrites existing .bak on Windows
            except Exception:
                pass
    return {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in _DEFAULTS.items()}


def _save(data: dict) -> None:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        # Atomik yazma: önce .tmp, sonra rename
        tmp = MEMORY_FILE.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(MEMORY_FILE)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"memory.json yazılamadı: {e}")


# ── Konuşma yönetimi ────────────────────────────────────────────────────────

def get_session_messages(session_id: str) -> list:
    data = _load()
    session = next((c for c in data.get("conversations", []) if c["id"] == session_id), None)
    return session.get("messages", []) if session else []


def add_message(session_id: str, role: str, content: str) -> None:
    data = _load()
    convos = data.setdefault("conversations", [])

    session = next((c for c in convos if c["id"] == session_id), None)
    if session is None:
        session = {"id": session_id, "started": datetime.now().isoformat(), "messages": []}
        convos.append(session)

    session["messages"].append({
        "role": role,
        "content": content,
        "ts": datetime.now().isoformat(),
    })
    session["last_updated"] = datetime.now().isoformat()

    # Oturum başına mesaj sayısını 500 ile sınırla
    if len(session["messages"]) > 500:
        session["messages"] = session["messages"][-500:]

    # Toplam konuşma sayısını 200 ile sınırla
    if len(convos) > 200:
        data["conversations"] = convos[-200:]

    _save(data)


def get_recent_sessions(n: int = 5) -> list:
    data = _load()
    return data.get("conversations", [])[-n:]


def clear_session(session_id: str) -> None:
    data = _load()
    data["conversations"] = [c for c in data.get("conversations", []) if c["id"] != session_id]
    _save(data)


# ── Proje yönetimi ────────────────────────────────────────────────────────────

def save_project(name: str, path: str, files: list, description: str = "") -> None:
    data = _load()
    projects = data.setdefault("projects", [])
    existing = next((p for p in projects if p["name"] == name), None)
    if existing:
        existing.update({"path": path, "files": files, "description": description,
                         "updated": datetime.now().isoformat()})
    else:
        projects.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "path": path,
            "files": files,
            "description": description,
            "created": datetime.now().isoformat(),
        })
    _save(data)


def get_projects() -> list:
    return _load().get("projects", [])


def save_file_info(path: str, description: str = "") -> None:
    data = _load()
    data.setdefault("files", {})[path] = {
        "last_seen": datetime.now().isoformat(),
        "description": description,
    }
    _save(data)


# ── Hatırlatıcı yönetimi ──────────────────────────────────────────────────────

def add_reminder(chat_id: int, text: str, when_iso: str) -> str:
    data = _load()
    rid = str(uuid.uuid4())[:8]
    data.setdefault("reminders", []).append({
        "id": rid,
        "chat_id": chat_id,
        "text": text,
        "when": when_iso,
        "created": datetime.now().isoformat(),
        "done": False,
    })
    _save(data)
    return rid


def get_pending_reminders() -> list:
    data = _load()
    now = datetime.now()
    result = []
    for r in data.get("reminders", []):
        if r.get("done") or not r.get("when"):
            continue
        try:
            if datetime.fromisoformat(r["when"]) <= now:
                result.append(r)
        except ValueError:
            pass
    return result


def mark_reminder_done(rid: str) -> None:
    data = _load()
    for r in data.get("reminders", []):
        if r["id"] == rid:
            r["done"] = True
    _save(data)


def list_reminders(chat_id: Optional[int] = None) -> list:
    data = _load()
    reminders = data.get("reminders", [])
    if chat_id is not None:
        reminders = [r for r in reminders if r.get("chat_id") == chat_id]
    return [r for r in reminders if not r.get("done")]


def delete_reminder(rid: str) -> bool:
    data = _load()
    before = len(data.get("reminders", []))
    data["reminders"] = [r for r in data.get("reminders", []) if r["id"] != rid]
    _save(data)
    return len(data["reminders"]) < before


# ── Öğrenilen bilgi yönetimi ──────────────────────────────────────────────────

def save_learned(url: str, title: str, summary: str, facts: list) -> None:
    """URL'den öğrenilen bilgiyi kalıcı hafızaya kaydet."""
    data = _load()
    learned = data.setdefault("learned", [])

    existing = next((l for l in learned if l.get("url") == url), None)
    if existing:
        existing.update({
            "title": title,
            "summary": summary[:2000],
            "facts": facts[:20],
            "updated": datetime.now().isoformat(),
        })
    else:
        learned.append({
            "url": url,
            "title": title,
            "summary": summary[:2000],
            "facts": facts[:20],
            "learned_at": datetime.now().isoformat(),
        })

    if len(learned) > 500:
        data["learned"] = learned[-500:]

    _save(data)


def search_learned(query: str, max_results: int = 3) -> list:
    """Öğrenilen bilgiler içinde anahtar kelime araması yap."""
    data = _load()
    learned = data.get("learned", [])
    if not learned:
        return []

    query_words = {w for w in query.lower().split() if len(w) > 2}
    if not query_words:
        return []

    scored = []
    for item in learned:
        text = " ".join([
            item.get("title", ""),
            item.get("summary", ""),
            " ".join(item.get("facts", [])),
            item.get("url", ""),
        ]).lower()
        score = sum(1 for w in query_words if w in text)
        if score > 0:
            scored.append((score, item))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [r[1] for r in scored[:max_results]]


def get_learned_count() -> int:
    return len(_load().get("learned", []))


# ── MemoryManager sınıfı (brain.py için sarmalayıcı) ─────────────────────────

class MemoryManager:
    def __init__(self, session_id: str):
        self.session_id = session_id

    def get_history(self, last_n: int = 20) -> list:
        return get_session_messages(self.session_id)[-last_n:]

    def add(self, role: str, content: str) -> None:
        add_message(self.session_id, role, content)

    def clear(self) -> None:
        clear_session(self.session_id)

    def summary_text(self) -> str:
        """Son 3 konuşmayı metin olarak özetle (sistem prompt'a ek olarak)."""
        recent = get_recent_sessions(3)
        if not recent:
            return ""
        lines = ["[Önceki konuşmalar:]"]
        for session in recent:
            for m in session.get("messages", [])[-4:]:
                role_label = "Sen" if m["role"] == "assistant" else "Kayra"
                lines.append(f"{role_label}: {m['content'][:200]}")
        return "\n".join(lines)
