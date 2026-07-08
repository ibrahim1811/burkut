# BÜRKÜT OS — Yol Haritası

> Sürüm: 1.0 · Tarih: 2026-07-08 · Bağlantılı: [00-prd.md](00-prd.md), [01-architecture.md](01-architecture.md)

## 1. Faz Tablosu

| Faz | Kapsam | Tahmin | Sürüm |
|---|---|---|---|
| **0 — Dokümantasyon** | PRD + 8 teknik doküman (`docs/burkut-os/`), jarvis-v2 superseded | ~1 hafta | v0.1 |
| **1 — Güvenlik + Temel** | Sır temizliği + rotasyon, `server/` FastAPI (:8765), SQLite şema (+ `devices` tablosu), memory.json migrasyonu, **Event Bus** (`core/events.py`), **Tool Dispatcher** (`ai/tools/`), **AI kişilik dosyaları** (`ai/prompts/`) | ~1 hafta | v0.1 |
| **2 — Memory Engine** | `memory/` paketi: FTS5 + embedding hybrid arama, ranking, context builder, brain entegrasyonu; `<EYLEM>` handler'larının dispatcher'a kademeli taşınması | ~2 hafta | v0.2 |
| **3 — Dashboard** | React + Vite + Tailwind; MVP sayfaları: System, Memory Timeline, AI Chat, Tasks/Reminders; WebSocket canlı veri + olay akışı | ~2 hafta | v0.3 (MVP) |
| **4.1 — Model Router** | `ai/router.py`: Groq varsayılan, Ollama fallback, opsiyonel ücretli; maliyet sayacı | ~2 hafta | v1.0 |
| **4.2 — Scheduler + Automation** | `scheduler/` (zaman tabanlı: 09:00 görev oku, 22:00 backup — ayrı modül) + `automation/` (olay/koşul/eylem; tetikleyiciler: Event Bus + Scheduler), DB'de kurallar, dashboard kural editörü | ~2-3 hafta | v1.0 |
| **4.3 — Planner/Executor** | `ai/planner.py` + `ai/executor.py`: çok adımlı görevler ("VSCode aç, projeyi tara, bug bul, GitHub issue oluştur") | ~2 hafta | v1.0 |
| **4.4 — Güvenlik sertleştirme** | git filter-repo sır temizliği, audit_log tüm kanallarda, TOTP 2FA, rate-limit FastAPI'ye | ~1 hafta | v1.0 |
| **4.5 — React Native Android** | Mevcut FastAPI'yi tüketir; Cloudflare Tunnel/Tailscale uzak erişim; FCM push | ~3-4 hafta | v1.0 |
| **5.1 — Vision/OCR** | RapidOCR (offline, ücretsiz) + Groq vision; "ekrandaki hata ne?" senaryoları | v2.0 |
| **5.2 — Proaktif AI** | Kullanım deseni analizi; overlay + Telegram öneri bildirimleri | v2.0 |
| **6 — Plugin System** | Manifest + Python entrypoint; Spotify/Discord/OBS ilk eklentiler. *Bilinçli erteleme: Memory, Dashboard ve Automation çekirdeği oturmadan eklenti API'si sabitlenemez* | v2.0+ |

Sıralama bağımlılığı (MVP içinde): **1 → 2 → 3** (FastAPI iskeleti olmadan dashboard olmaz; SQLite olmadan Memory Engine olmaz).

## 2. Çıkış Kriterleri (Definition of Done)

### Faz 0
- [ ] 8 doküman `docs/burkut-os/` altında tamamlanmış
- [ ] `docs/plans/jarvis-v2/` superseded olarak işaretlenmiş
- [ ] DB şeması ve API sözleşmesi yazılı — Faz 1 kodu bunlara referansla yazılabilir

### Faz 1
- [ ] `config.json`'da hiçbir gerçek sır yok; `config.example.json` + `.gitignore` güncel
- [ ] Telegram bot token **rotate edilmiş**, Render env + yerel `.env` eşzamanlı güncellenmiş
- [ ] `curl -H "X-Burkut-Token: ..." http://localhost:8765/api/v1/system/stats` → geçerli JSON
- [ ] `data/burkut.db` şema oluşmuş (WAL); `migrate_memory.py` çalıştırılmış, `memory.json.bak` duruyor
- [ ] Regresyon: Telegram `/durum` ve temel komutlar çalışıyor

### Faz 2
- [ ] Türkçe doğal dil sorgusu (`python -m memory.search "sınav"`) ilgili anıyı ilk 3 sonuçta döndürüyor
- [ ] Sohbette geçmiş bir anının bağlama otomatik enjekte edildiği gözlemleniyor
- [ ] `BURKUT_EMBEDDINGS=off` ile FTS-only mod sorunsuz
- [ ] Embedding gecikmesi voice/widget'ı bloklamıyor (lazy-load + arkaplan batch)

### Faz 3 (MVP çıkışı)
- [ ] Tarayıcıda `localhost:8765` → canlı CPU/RAM/GPU grafiği ≤2 sn gecikmeyle akıyor
- [ ] Bellek sayfası: arama + CRUD; Sohbet sayfası BurkutBrain'e bağlı; Hatırlatıcılar listeleniyor
- [ ] Telefon tarayıcısından LAN üzerinden erişim çalışıyor
- [ ] Tüm Telegram komutları smoke-test'ten geçiyor

### Faz 4.1 — Model Router
- [ ] Groq kesintisinde Ollama'ya otomatik fallback
- [ ] `<EYLEM>` protokolü tüm sağlayıcılarda aynen çalışıyor
- [ ] Maliyet sayacı + günlük limit; ücretli model yalnızca anahtar tanımlıysa ve onayla

### Faz 4.2 — Automation Engine
- [ ] Cron, sistem eşiği (örn. CPU>90), uygulama açılışı trigger'ları çalışıyor
- [ ] Kural CRUD dashboard'dan; `automations` tablosu + `last_run/run_count` izleniyor
- [ ] Mevcut `core/scheduler.py` motora emilmiş, hatırlatıcılar kırılmamış

### Faz 4.3 — Güvenlik
- [ ] Git geçmişinde sır taraması temiz (filter-repo sonrası)
- [ ] Her komut yolu (Telegram/API/voice/automation) `audit_log`'a yazıyor
- [ ] Kritik eylemler (güç, dosya silme) TOTP onayı istiyor

### Faz 4.4 — Android
- [ ] Canlı PC durumu, dosya transferi, AI sohbet mobilde çalışıyor
- [ ] Uzak erişim tüneli kurulu; FCM bildirimleri geliyor

## 3. Gelecek Sürümler (v2.0+)

- **Vision:** gerçek zamanlı ekran izleme, "bu butona bas" UI otomasyonu, uygulama içi bağlam farkındalığı.
- **Plugin ekosistemi:** Chrome (DevTools), Steam, WhatsApp, Home Assistant, Arduino/ESP32.
- **Proaktif zekâ:** ders/sınav takvimi farkındalığı, kod projesi devamlılık önerileri, sağlık/mola hatırlatmaları.
- **Ses geliştirmeleri:** kesintisiz (barge-in) diyalog, ses profili, çoklu mikrofon yönetimi.
- **Opsiyonel:** repo adının `BurkutOS` olarak değişmesi (v1.0 sonrası, kırıcı olmayan zamanda).

## 4. İlkeler

- Her faz sonunda mevcut Telegram komutları smoke-test edilir; regresyon = fazın bitmemiş sayılması.
- Ücretsiz katman sınırları (Groq rate limit, Render saat kotası, 512MB Render RAM) her fazda tasarım kısıtıdır.
- Yeni bağımlılıklar `sys_platform == "win32"` işaretiyle eklenir — Render build'i asla şişmez.
