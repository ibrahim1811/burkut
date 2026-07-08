# Bürküt OS — Veritabanı Tasarımı

> Tek dosya: `data/burkut.db` (SQLite, WAL modu). İlgili dokümanlar: `02-memory-engine.md`, `04-api.md`.

## 1. Genel İlkeler

- **SQLite** seçildi: sıfır kurulum, tek dosya yedekleme, FTS5 dahili, tek kullanıcılı sistem için fazlasıyla yeterli. PostgreSQL ancak çok cihazlı senkronizasyon gündeme gelirse değerlendirilir.
- **WAL modu** (`PRAGMA journal_mode=WAL`): bot thread'leri + FastAPI + widget aynı DB'yi okurken yazma kilitlenmesini önler.
- **Tek-yazıcı kuyruk deseni:** tüm yazımlar `memory/store.py` içindeki tek bir writer thread'in kuyruğundan geçer; okumalar serbesttir. SQLite'ta eşzamanlı çok-yazıcı çekişmesini kökten çözer.
- `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`.
- Tarihler ISO-8601 UTC TEXT (`2026-07-08T16:00:00Z`); JSON kolonları TEXT içinde JSON.

## 2. Şema (DDL)

```sql
-- ── Hafıza çekirdeği ─────────────────────────────────────────────
CREATE TABLE memories (
    id            INTEGER PRIMARY KEY,
    kind          TEXT NOT NULL CHECK (kind IN ('fact','preference','event','note','project')),
    content       TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'auto',   -- telegram|voice|dashboard|auto|migration
    importance    REAL NOT NULL DEFAULT 0.5,      -- 0.0–1.0
    access_count  INTEGER NOT NULL DEFAULT 0,
    embedding     BLOB,                            -- float32[384] LE; NULL = henüz embed edilmedi
    created_at    TEXT NOT NULL,
    last_accessed TEXT,
    expires_at    TEXT,                            -- NULL = kalıcı
    deleted       INTEGER NOT NULL DEFAULT 0,      -- soft-delete ("unut")
    metadata      TEXT                             -- JSON: {url, file, tags...}
);
CREATE INDEX idx_memories_kind ON memories(kind) WHERE deleted = 0;

-- FTS5 gölge tablosu (external content) — Türkçe diakritik toleransı
CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    content='memories', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
-- senkron trigger'ları: INSERT/UPDATE/DELETE → memories_fts

-- ── Konuşmalar (kısa süreli bellek) ──────────────────────────────
CREATE TABLE conversations (
    id           INTEGER PRIMARY KEY,
    channel      TEXT NOT NULL,                    -- telegram|voice|dashboard|widget
    started_at   TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    summary      TEXT                              -- oturum kapanınca LLM özeti
);
CREATE TABLE messages (
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT NOT NULL,
    ts              TEXT NOT NULL
);
CREATE INDEX idx_messages_conv ON messages(conversation_id, ts);

-- ── Görevler & hatırlatıcılar ────────────────────────────────────
CREATE TABLE reminders (
    id           INTEGER PRIMARY KEY,
    text         TEXT NOT NULL,
    remind_at    TEXT NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'all',      -- tts|telegram|overlay|all
    fired        INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed
    due_at       TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT,
    source       TEXT NOT NULL DEFAULT 'dashboard'
);

-- ── Automation Engine (Faz 2b'de kullanılır, şema baştan hazır) ──
CREATE TABLE automations (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1,
    trigger    TEXT NOT NULL,   -- JSON: {"type":"cron","expr":"0 9 * * *"} | {"type":"threshold","metric":"cpu","op":">","value":90}
    conditions TEXT,             -- JSON dizi
    actions    TEXT NOT NULL,    -- JSON: [{"action":"notify","params":{...}}]
    last_run   TEXT,
    run_count  INTEGER NOT NULL DEFAULT 0
);

-- ── Güvenlik / izleme ────────────────────────────────────────────
CREATE TABLE audit_log (
    id      INTEGER PRIMARY KEY,
    ts      TEXT NOT NULL,
    actor   TEXT NOT NULL,      -- telegram:<user_id>|dashboard|voice|automation:<id>
    channel TEXT NOT NULL,
    action  TEXT NOT NULL,
    params  TEXT,               -- JSON (sır içermez)
    result  TEXT,
    success INTEGER NOT NULL
);
CREATE INDEX idx_audit_ts ON audit_log(ts);

-- ── Ayarlar (sır OLMAYAN yapılandırma) ───────────────────────────
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL         -- JSON
);
```

> **Not:** `memory_vectors` ayrı tablosu (sqlite-vec) MVP'de yok; embedding'ler `memories.embedding` BLOB'unda. Veri 100k satırı aşarsa sqlite-vec'e taşıma migrasyonu yazılır (bkz. `02-memory-engine.md §4`).

## 3. Şema Migrasyonları

`PRAGMA user_version` tabanlı basit sistem (`memory/store.py`):

```python
MIGRATIONS = {1: _v1_initial, 2: _v2_add_x, ...}
# açılışta: user_version < max → sıradaki migrasyonlar transaction içinde uygulanır
```

- Her migrasyon tek transaction; başarısızlıkta rollback.
- Migrasyon öncesi otomatik dosya kopyası: `data/burkut.db.pre-vN`.

## 4. memory.json → SQLite Göç Eşlemesi

`migrate_json.py` (bot kapalıyken, tek seferlik):

| memory.json alanı | Hedef tablo | Not |
|---|---|---|
| `conversations[]` | `conversations` + `messages` | session → conversation; mesajlar role/content/ts ile |
| `projects{}` | `memories (kind='project')` | proje adı+durumu content'e; metadata'ya ham JSON |
| `files{}` | `memories (kind='note', metadata.file)` | |
| `reminders[]` | `reminders` | fired durumu korunur |
| öğrenilen web kaynakları (key-facts) | `memories (kind='fact', source='migration', metadata.url)` | her key-fact ayrı satır |

Göç sonrası: `memory.json` → `memory.json.bak` (silinmez). Dual-write dönemi ve kapanış için bkz. `02-memory-engine.md §8`.

## 5. Yedekleme

- WAL checkpoint sonrası `data/burkut.db` tek dosya kopyalanabilir; haftalık otomatik yedek Faz 2b'de automation olarak tanımlanır.
- `audit_log` 90 günden eski kayıtlar aylık temizlenir (settings'ten ayarlanabilir).
