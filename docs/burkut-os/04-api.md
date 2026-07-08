# Bürküt OS — API Sözleşmesi (FastAPI)

> Yerel sunucu: `http://localhost:8765` — `server/` paketi, `local/pc_agent.py` içinden thread olarak başlar.
> Render'daki Flask relay (`/agent/poll`, `/agent/result`) **bu sözleşmenin dışındadır ve değişmez.**

## 1. Genel Kurallar

- **Base path:** `/api/v1`
- **Auth:** her istekte `X-Burkut-Token: <token>` header'ı. Token `.env` → `DASHBOARD_TOKEN`. WebSocket'te ilk mesaj `{"token": "..."}` veya `?token=` query param.
- **İçerik:** `application/json; charset=utf-8`
- **Hata biçimi (tüm endpoint'ler):**

```json
{ "error": { "code": "unauthorized", "message": "Geçersiz token" } }
```

| HTTP | code | Anlam |
|---|---|---|
| 401 | `unauthorized` | Token yok/yanlış |
| 404 | `not_found` | Kayıt yok |
| 422 | `validation_error` | Gövde şemaya uymuyor (FastAPI detayı `error.details` içinde) |
| 429 | `rate_limited` | İstek limiti (utils/security.py deseni) |
| 500 | `internal` | Beklenmeyen hata (audit_log'a yazılır) |

- **CORS:** production'da yok (dashboard aynı origin'den static mount). Geliştirmede yalnız `http://localhost:5173` (Vite) izinli.
- **Mobil notu (Faz 2d):** sözleşme React Native istemcisi düşünülerek tasarlandı — tüm yanıtlar self-contained JSON, sayfalama `?limit=&offset=`, WS protokolü tip alanlı zarf kullanır. Uzak erişim Tailscale/Cloudflare Tunnel ile aynı sözleşme üzerinden.

## 2. REST Endpoint'leri

### Sistem

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/v1/system/stats` | Anlık CPU/RAM/GPU/disk/ağ (kaynak: `core/system_info.py`) |
| GET | `/api/v1/system/processes?limit=50&sort=cpu` | Süreç listesi |
| POST | `/api/v1/system/processes/{pid}/kill` | Süreç sonlandır (audit_log'a yazar) |

`GET /system/stats` yanıtı:

```json
{
  "ts": "2026-07-08T16:00:00Z",
  "cpu": { "percent": 23.4, "per_core": [12.0, 34.1], "freq_mhz": 3400 },
  "ram": { "total_mb": 16384, "used_mb": 9011, "percent": 55.0 },
  "gpu": { "name": "RTX 3060", "util_percent": 12, "mem_used_mb": 1800, "temp_c": 51 },
  "disk": [ { "mount": "C:\\", "total_gb": 512, "used_gb": 300, "percent": 58.6 } ],
  "net": { "sent_kbps": 120.5, "recv_kbps": 890.2 }
}
```

### Bellek (Memory Engine)

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/v1/memory?kind=fact&limit=20&offset=0` | Anı listesi (yeniden eskiye) |
| POST | `/api/v1/memory` | Anı ekle `{kind, content, importance?, metadata?}` |
| PATCH | `/api/v1/memory/{id}` | Güncelle (content/importance) |
| DELETE | `/api/v1/memory/{id}` | Soft-delete ("unut") |
| GET | `/api/v1/memory/search?q=sınav&limit=10` | Hybrid arama (bkz. 02-memory-engine.md) |

`GET /memory/search` yanıtı:

```json
{
  "query": "sınav",
  "mode": "hybrid",              // hybrid | fts_only (kill-switch aktifse)
  "results": [
    { "id": 42, "kind": "event", "content": "8 Temmuz'da fizik sınavı",
      "score": 0.87, "importance": 0.7, "created_at": "2026-07-01T10:00:00Z" }
  ]
}
```

### Sohbet

| Metot | Yol | Açıklama |
|---|---|---|
| POST | `/api/v1/chat` | `{"message": "..."}` → `BurkutBrain` yanıtı |
| GET | `/api/v1/chat/history?limit=50` | Dashboard kanalı konuşma geçmişi |

`POST /chat` yanıtı:

```json
{
  "reply": "Tamamdır, Spotify açıldı.",
  "actions": [ { "action": "open_app", "params": {"name": "spotify"}, "success": true } ],
  "memories_used": [42, 17],
  "conversation_id": 7
}
```

### Hatırlatıcılar

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/v1/reminders?include_fired=false` | Liste |
| POST | `/api/v1/reminders` | `{text, remind_at, channel?}` |
| DELETE | `/api/v1/reminders/{id}` | Sil |

## 3. WebSocket Protokolü

Tüm WS mesajları tip alanlı zarf kullanır: `{"type": "...", "data": {...}}`.

### `WS /ws/stats`
- Bağlantı → auth → sunucu **2 sn'de bir** `{"type":"stats","data":{<GET /system/stats yanıtıyla aynı gövde>}}` push eder.
- İstemci `{"type":"set_interval","data":{"seconds":5}}` ile aralığı değiştirebilir (min 1, max 60).

### `WS /ws/events`
- Olay akışı: bildirimler, hatırlatıcı tetiklenmesi, automation çalışması, yeni anı kaydı.

```json
{ "type": "event", "data": { "event": "reminder_fired", "id": 3, "text": "Sınava çalış", "ts": "..." } }
{ "type": "event", "data": { "event": "memory_added", "id": 51, "kind": "fact" } }
```

- Heartbeat: sunucu 30 sn'de bir `{"type":"ping"}`; istemci `{"type":"pong"}` döner. 90 sn yanıtsızlıkta bağlantı kapatılır.

## 4. Sunucu Yerleşimi

```
server/
├── app.py        # FastAPI app + lifespan (writer thread, WS broadcast görevi) + static mount (dashboard/dist)
├── auth.py       # X-Burkut-Token dependency + WS auth
├── ws.py         # /ws/stats, /ws/events yöneticisi
└── routes/
    ├── system.py   # core/system_info.py, core/process_manager.py sarmalayıcıları
    ├── memory.py   # memory/ paketi CRUD + search
    ├── chat.py     # ai/brain.py BurkutBrain köprüsü
    └── reminders.py
```

- Port: **8765** (config: `settings` tablosu / `.env` → `BURKUT_PORT`).
- Başlatma: `pc_agent.py` açılışında `threading.Thread(target=uvicorn.run, daemon=True)`; `--no-server` bayrağıyla kapatılabilir.
- LAN erişimi: `0.0.0.0` bind + Windows Firewall'da 8765 izni (kurulum notu `05-dashboard.md`'de). Telefondan `http://<pc-ip>:8765`.
- Bağımlılıklar `requirements.txt`'e `sys_platform == "win32"` işaretiyle eklenir → Render build etkilenmez.
