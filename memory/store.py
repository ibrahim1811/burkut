import json
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "burkut.db"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'note',          -- fact|preference|event|note|project
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',      -- telegram|voice|dashboard|auto|manual|migration
    importance REAL NOT NULL DEFAULT 0.5,
    access_count INTEGER NOT NULL DEFAULT 0,
    embedding BLOB,
    metadata TEXT,
    created_at REAL NOT NULL,
    last_accessed REAL,
    expires_at REAL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF content ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL DEFAULT 'telegram',
    started_at REAL NOT NULL,
    last_updated REAL NOT NULL,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, ts);

CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    chat_id INTEGER,
    text TEXT NOT NULL,
    when_iso TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    due_at REAL,
    remind_at REAL,
    source TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);

CREATE TABLE IF NOT EXISTS automations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    trigger TEXT NOT NULL,
    conditions TEXT,
    actions TEXT NOT NULL,
    last_run REAL,
    run_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    actor TEXT NOT NULL,
    channel TEXT NOT NULL,
    action TEXT NOT NULL,
    params TEXT,
    result TEXT,
    success INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                _migrate(conn)
                _conn = conn
    return _conn


_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,          -- 'kayra-pc', 'telefon', 'esp32-salon'
    type TEXT NOT NULL DEFAULT 'other', -- pc|phone|tablet|laptop|esp32|arduino|other
    platform TEXT,                      -- windows|android|esp|...
    address TEXT,                       -- ip / mac / telegram chat_id
    status TEXT NOT NULL DEFAULT 'unknown',  -- online|offline|unknown
    last_seen REAL,
    metadata TEXT
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript(_SCHEMA)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    if version < 2:
        conn.executescript(_SCHEMA_V2)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()


def write(sql: str, params: tuple = ()) -> int:
    conn = get_conn()
    with _lock:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def read(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return get_conn().execute(sql, params).fetchall()


def add_memory(content: str, kind: str = "note", source: str = "manual",
               importance: float = 0.5, metadata: dict | None = None) -> int:
    return write(
        "INSERT INTO memories (kind, content, source, importance, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (kind, content, source, importance,
         json.dumps(metadata, ensure_ascii=False) if metadata else None, time.time()),
    )


def audit(actor: str, channel: str, action: str, params: dict | None = None,
          result: str = "", success: bool = True) -> None:
    write(
        "INSERT INTO audit_log (ts, actor, channel, action, params, result, success) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time(), actor, channel, action,
         json.dumps(params, ensure_ascii=False) if params else None, result, int(success)),
    )
