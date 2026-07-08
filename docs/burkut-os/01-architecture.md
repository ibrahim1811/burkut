# BÜRKÜT OS — Sistem Mimarisi

> Sürüm: 1.0 · Tarih: 2026-07-08 · Bağlantılı: [00-prd.md](00-prd.md), [03-database.md](03-database.md), [04-api.md](04-api.md)

## 1. Katmanlı Mimari (Hedef)

```
┌─────────────────────────────────────────────────────────────┐
│                        ARAYÜZLER                             │
│  Dashboard (React)   Telegram Bot   Mobile App (RN, Faz 2d) │
│  Widget (PySide6)    Voice ("Bürküt")                        │
├─────────────────────────────────────────────────────────────┤
│                       API LAYER                              │
│  FastAPI (yerel :8765, token auth, REST + WebSocket)         │
│  Flask Relay (Render, /agent/poll · /agent/result)           │
├─────────────────────────────────────────────────────────────┤
│                     EVENT BUS (Faz 1)                        │
│  core/events.py — pub/sub · PC_BOOTED · COMMAND_RECEIVED ·   │
│  TOOL_EXECUTED · MEMORY_ADDED · REMINDER_DUE · AI_RESPONSE   │
│  (saf stdlib → Render'da da import güvenli)                  │
├─────────────────────────────────────────────────────────────┤
│                        CORE AI                               │
│  BurkutBrain (Groq) · Tool Dispatcher (ai/tools, Faz 1) ·    │
│  Model Router (Faz 4.1) · planner/executor (Faz 4) ·         │
│  prompts/ kişilik dosyaları · <EYLEM>{json}</EYLEM>          │
├─────────────────────────────────────────────────────────────┤
│                     MEMORY ENGINE                            │
│  SQLite + FTS5 + embedding (MiniLM) · hybrid search ·        │
│  ranking · context builder (RAG)                             │
├─────────────────────────────────────────────────────────────┤
│   SCHEDULER (Faz 4.2) · AUTOMATION (Faz 4.2) · VISION (5.1)  │
│  zaman tabanlı görevler · olay/koşul/eylem kuralları ·       │
│  OCR + ekran analizi (Automation, Scheduler'ı ve Event       │
│  Bus'ı tetikleyici olarak kullanır)                          │
├─────────────────────────────────────────────────────────────┤
│          DEVICE MANAGER (core/) + DEVICE REGISTRY (DB)       │
│  sistem · süreç · güç · dosya · pencere · pano · ses ·       │
│  parlaklık · klavye/fare · kamera · bildirim · devices       │
│  tablosu (PC/telefon/ESP32/Arduino envanteri)                │
├─────────────────────────────────────────────────────────────┤
│              PLUGIN SYSTEM (Faz 6) · DESKTOP AGENT           │
│  manifest + hook API · local/pc_agent.py (poll + yürütme)    │
├─────────────────────────────────────────────────────────────┤
│                        DATABASE                              │
│  data/burkut.db (SQLite WAL) · data/offline_queue/           │
└─────────────────────────────────────────────────────────────┘
```

## 2. Üç Çalışma Ortamı

```
┌──────────── RENDER (bulut, free tier) ────────────┐
│ main.py                                            │
│  ├─ Telegram bot (long polling)                    │
│  └─ Flask relay  /health /agent/poll /agent/result │
│     (X-Agent-Token korumalı, donanım erişimi yok)  │
└───────────────────────▲────────────────────────────┘
                        │ HTTPS poll (~1.5 sn)
┌───────────────────────┴──── YEREL PC (Windows) ────┐
│ local/pc_agent.py (30+ komut handler)               │
│  ├─ FastAPI server thread (:8765)  ← YENİ (Faz 1)   │
│  │   ├─ REST /api/v1/*  ·  WS /ws (canlı metrik)    │
│  │   └─ dashboard/ build (static mount)             │
│  ├─ widget/ (PySide6 overlay + tray)                │
│  ├─ voice/ (Vosk wake-word, Whisper STT, edge-tts)  │
│  ├─ ai/ (BurkutBrain + Memory Engine)               │
│  ├─ core/ (tüm Windows donanım kontrolü)            │
│  └─ data/burkut.db (SQLite)                         │
└───────────────────────▲────────────────────────────┘
                        │ HTTP/WS (localhost veya LAN)
┌───────────────────────┴──── TARAYICI ──────────────┐
│ React Dashboard (cyberpunk tema)                    │
│  Sistem · Bellek · Sohbet · Hatırlatıcılar          │
└─────────────────────────────────────────────────────┘
```

Kritik karar: **FastAPI ayrı süreç değil, `pc_agent.py` içinde thread** olarak başlar. Render'daki Flask relay'e dokunulmaz; dashboard trafiği Render'a hiç uğramaz (gecikme ve free-tier kotası korunur).

## 3. Veri Akışları

### 3.1 Telegram → Render → Agent (mevcut, değişmiyor)
```
Kullanıcı (Telegram) → bot/handlers.py (Render)
  → agent_relay.py komut kuyruğu
  → pc_agent.py GET /agent/poll (1.5 sn)
  → komut yerelde yürütülür (core/*)
  → POST /agent/result → handlers yanıtı Telegram'a döner
```

### 3.2 Dashboard → FastAPI → Core (yeni, Faz 1–3)
```
Tarayıcı → GET/POST /api/v1/*  (X-Burkut-Token)
  → server/routes/* → core/system_info.py vb. (mevcut fonksiyonlar sarılır)
  → JSON yanıt
Tarayıcı ⇆ WS /ws → server/ws.py → 2 sn'de bir psutil metrikleri push
```

### 3.3 Voice → Brain → Core (mevcut; Faz 2'de bellek enjeksiyonu eklenir)
```
Mikrofon → wake_word (Vosk) → audio_recorder → speech_recognizer (Whisper)
  → voice_assistant NLU → ai/brain.py
       └─ (Faz 2) memory/context_builder → ilgili anılar sistem prompt'una
  → Groq yanıtı + <EYLEM>{json}</EYLEM> → core/* yürütme → edge-tts sesli yanıt
```

### 3.4 Bellek yazma (yeni, Faz 2)
```
Her sohbet turu → brain yanıtı + yan çıktı olarak "anı adayı"
  → memory/store.py (SQLite: memories + memories_fts + embedding BLOB)
  → arkaplan thread'de lazy batch embed
```

### 3.5 Event Bus (yeni, Faz 1) — "birbirini çağıran modüller" yerine olay akışı
```
core → events → diğer modüller

Örnek: PC_BOOTED
pc_agent.py başlar → bus.emit(PC_BOOTED)
  ├→ Dashboard (WS /ws/events) canlı güncellenir
  ├→ Automation (Faz 4.2) açılış kuralları tetiklenir
  ├→ Memory Engine olayı kaydeder
  └→ Telegram'a bildirim gider
```
Modüller birbirini doğrudan çağırmak yerine olay yayınlar; dinleyen dinler.
`core/events.py` saf stdlib olduğundan Render'da da güvenle import edilir —
ama dinleyicilerin donanım işi yapanları yalnızca yerel PC'de abone olur.

### 3.6 Tool Calling (yeni, Faz 1) — AI asla doğrudan Windows API çağırmaz
```
AI (Groq yanıtı) → Tool Dispatcher (ai/tools/dispatcher.py)
  → @tool registry'den fonksiyon bulunur
  → tool (open_program, volume_set, ...) → core/* → Windows
  → sonuç + audit_log kaydı + TOOL_EXECUTED olayı
```
İlk tool'lar: `open_program`, `open_url`, `close_program`, `volume_set`, `volume_mute`.
`brain.py`'daki `<EYLEM>` handler'ları Faz 2'de kademeli olarak dispatcher'a taşınır.
Kazanım: tek yetki/audit noktası (güvenlik) + yeni yetenek = tek dosya (genişletilebilirlik).

## 4. Mevcut vs. Hedef

| Boyut | Mevcut (PcBot) | Hedef (Bürküt OS) |
|---|---|---|
| AI sağlayıcı | Yalnızca Groq (llama-3.3-70b) | Model Router: Groq varsayılan + Ollama fallback + opsiyonel Claude/GPT |
| Bellek | memory.json (düz JSON, arama yok) | SQLite + FTS5 + embedding, hybrid arama, ranking, RAG |
| API | Flask relay (yalnız agent köprüsü) | + FastAPI yerel REST/WS katmanı (:8765) |
| Arayüz | Telegram + widget + voice | + React Dashboard + Android app (Faz 2d) |
| Vision | Screenshot/webcam çekimi (analiz yok) | + OCR + LLM ekran analizi (Faz 3a) |
| Otomasyon | Sabit kodlu (scheduler, hatırlatıcı) | + IFTTT tarzı kural motoru (Faz 2b) |
| Genişletme | Monolitik modüller | + Plugin API (Faz 3b) |
| Sırlar | config.json'da commit'li | .env + rotate + audit log |

## 5. Modül Sorumluluk Tablosu

### Mevcut (Faz 1'de dokunulmaz*)
| Modül | Sorumluluk |
|---|---|
| `bot/` | Telegram komut/callback işleme, agent_relay kuyruk köprüsü |
| `core/` | Windows donanım/OS kontrolü: sistem bilgisi, süreç, güç, dosya, pencere, pano, ses, parlaklık, klavye/fare, kamera, overlay bildirim, offline kuyruk |
| `ai/` | BurkutBrain (Groq + EYLEM ayrıştırma), memory.py (*adapter'a dönüşür), prompts/ (kişilik: system_prompt.md + conversation_rules.md + memory_rules.md — `_load_system_prompt()` dosyadan yükler), tools/ (dispatcher + tool'lar), calendar_mgr, news_weather, web_reader |
| `voice/` | Wake-word (Vosk), STT (Groq Whisper), TTS (edge-tts), hotkey, NLU |
| `widget/` | PySide6 masaüstü overlay, tray, canlı stats, AI sohbet penceresi |
| `local/` | pc_agent.py: relay poll döngüsü + komut yürütme (+ Faz 1'de FastAPI thread başlatma) |
| `utils/` | config_manager (env geçişi burada), security (yetki/rate-limit), logger, helpers |
| `main.py` | Render giriş noktası: bot polling + Flask relay |

### Planlanan
| Modül | Faz | Sorumluluk |
|---|---|---|
| `core/events.py` | 1 ✅ | Event Bus: pub/sub, olay geçmişi (deque 200), standart olay adları; saf stdlib |
| `ai/tools/` | 1 ✅ | Tool Dispatcher (@tool registry, dispatch → audit + TOOL_EXECUTED) + ilk tool'lar |
| `ai/prompts/` | 1 ✅ | Kişilik dosyaları: system_prompt.md, conversation_rules.md, memory_rules.md |
| `server/` | 1 | FastAPI app, auth middleware, REST route'ları, WS metrik + olay push, dashboard static mount |
| `memory/` | 2 | store (SQLite+FTS5+devices), embedder (MiniLM, kill-switch), search (hybrid), ranker, context_builder |
| `dashboard/` | 3 | React + Vite + Tailwind SPA; MVP: System/Memory Timeline/AI Chat/Tasks — hedef: 9 bölümlü OS paneli |
| `ai/router.py` | 4.1 | Görev tipine göre model seçimi, maliyet sayacı, fallback zinciri |
| `scheduler/` | 4.2 | Zaman tabanlı görevler (09:00 görev oku, 22:00 backup); Automation'dan ayrı modül |
| `automation/` | 4.2 | Olay/koşul/eylem motoru; tetikleyiciler: Event Bus + Scheduler; kurallar DB'de, editör dashboard'da |
| `ai/planner.py` + `ai/executor.py` | 4 | Çok adımlı görev planlama/yürütme ("VSCode aç, projeyi tara, bug bul, GitHub issue oluştur") |
| `vision/` | 5.1 | RapidOCR + screenshot analizi, UI element tespiti |
| `plugins/` | 6 | Manifest + Python entrypoint sözleşmesi; EYLEM uzayına ve dashboard'a kayıt |

**Hedef AI Core yapısı** (brain.py tek dosya olarak büyütülmez):
```
ai/
  router.py        # model seçimi (Faz 4.1)
  planner.py       # çok adımlı görev planlama (Faz 4)
  executor.py      # plan adımlarını tool'larla yürütme (Faz 4)
  memory.py        # adapter → memory/ paketi
  context.py       # bağlam derleme (Faz 2'de memory/context_builder ile başlar)
  conversation.py  # oturum/diyalog yönetimi
  prompts/         # kişilik (Faz 1 ✅)
  tools/           # tool dispatcher + tool'lar (Faz 1 ✅)
```

## 6. Mimari İlkeler

1. **Adapter deseni ile evrim:** yeni modül eklenir → eski modül adapter olur → bir sonraki fazda emekli edilir. Big-bang rename yok.
2. **İmza sözleşmesi:** `ai/memory.py`'ın mevcut fonksiyon imzaları korunur; içi SQLite'a yönlenir — brain/handlers/widget değişmeden çalışır.
3. **Yerel öncelik:** Donanım verisi ve bellek asla Render'a gitmez; Render yalnızca Telegram köprüsü.
4. **Tek yazıcı:** SQLite WAL modu + yazma işlemleri tek kuyruk üzerinden (bot thread + FastAPI + widget eşzamanlılığı).
5. **Kademeli bozulma:** embedding yoksa FTS-only arama; Groq erişilemezse (Faz 4.1 sonrası) Ollama fallback; internet yoksa offline kuyruk.
6. **Olay güdümlü gevşek bağlılık:** modüller birbirini doğrudan çağırmak yerine Event Bus üzerinden haberleşir; yeni modül eklemek = olaya abone olmak.
7. **Tek eylem kapısı:** AI'nin tüm PC eylemleri Tool Dispatcher'dan geçer — yetki kontrolü, audit ve rate-limit tek noktada.
