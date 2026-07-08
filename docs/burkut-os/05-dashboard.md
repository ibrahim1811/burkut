# 05 — Dashboard Spesifikasyonu

## Genel Bakış
Bürküt OS'un görsel kontrol merkezi. Tarayıcıda çalışır, yerel FastAPI sunucusundan (`http://localhost:8765`) beslenir. Cyberpunk estetiği: koyu zemin, neon vurgular, glow efektleri.

## Teknoloji
| Katman | Seçim | Gerekçe |
|---|---|---|
| Framework | React 18 + TypeScript | React Native (Faz 5) ile kod/komponent sinerjisi |
| Build | Vite | Hızlı dev server, kolay proxy |
| Stil | Tailwind CSS | Utility-first, tema token'ları ile cyberpunk paleti |
| Grafik | Recharts | Canlı çizgi/alan grafikleri, hafif |
| Canlı veri | WebSocket (`/ws/stats`) | 2 sn'de bir push, polling yok |

## Tasarım Dili — Cyberpunk
- **Zemin:** `#0a0e17` (near-black, mavi alt ton), panel: `#111827/80` + blur
- **Neon vurgular:** cyan `#22d3ee` (birincil), magenta `#e879f9` (ikincil), lime `#a3e635` (başarı), amber `#fbbf24` (uyarı)
- **Glow:** kritik değerlerde `box-shadow: 0 0 12px <neon>` + `text-shadow`; aşırı kullanma — sadece aktif/kritik öğelerde
- **Tipografi:** başlıklar monospace (`JetBrains Mono` / `Share Tech Mono`), gövde `Inter`
- **Çizgiler:** 1px neon border, köşelerde clip-path kesikleri (cyberpunk çerçeve hissi)
- Karanlık tema tek ve varsayılan; açık tema kapsam dışı

## Sayfalar

### 1. Sistem (`/`)
- **StatCard** ×4: CPU %, RAM %, GPU % (pynvml), Disk % — anlık değer + mini sparkline
- **LiveChart**: son 5 dk CPU/RAM/GPU çizgi grafiği (recharts `AreaChart`, 2 sn tick)
- **NetworkPanel**: upload/download hızı
- **ProcessTable** (opsiyonel MVP+): ilk 10 süreç, CPU/RAM sıralı
- Veri kaynağı: `WS /ws/stats` — bağlantı koparsa otomatik reconnect (exponential backoff), "OFFLINE" glow badge

### 2. Bellek (`/memory`)
- **SearchBar**: semantic + FTS hybrid arama (`GET /api/v1/memory/search?q=`)
- **MemoryCard** listesi: içerik, tür (fact/preference/event/note), önem skoru, tarih; hover'da neon border
- **CRUD**: yeni anı ekleme modal'ı (`POST /api/v1/memory`), düzenleme, silme (onaylı)
- Boş durum: "Bürküt henüz bunu öğrenmedi" mesajı

### 3. Sohbet (`/chat`)
- Mesaj listesi + input; `POST /api/v1/chat` → BurkutBrain yanıtı
- Kullanıcı balonu cyan kenar, Bürküt balonu magenta kenar
- Yanıt beklerken neon "typing" göstergesi
- Konuşma geçmişi SQLite `conversations`/`messages` üzerinden yüklenir

### 4. Hatırlatıcılar (`/reminders`)
- Liste: zaman, metin, durum (bekliyor/tetiklendi)
- Ekle/sil (`/api/v1/reminders`)
- Mevcut `ai/calendar_mgr.py` zamanlayıcısıyla aynı tabloyu paylaşır

## Ortak Komponentler
`Layout` (sidebar nav + durum çubuğu: WS bağlantı, agent online, AI sağlayıcı), `StatCard`, `LiveChart`, `NeonPanel`, `TokenGate` (auth ekranı).

## Kimlik Doğrulama
- İlk açılışta token girişi → `localStorage.burkut_token`
- Tüm REST isteklerinde `X-Burkut-Token` header; WS bağlantısında `?token=` query param
- 401 → token ekranına düşür

## Servis Modeli
- **Prod:** `npm run build` → `dashboard/dist` → FastAPI `StaticFiles(directory=..., html=True)` mount → `http://localhost:8765` tek origin, **CORS gerekmez**
- **Dev:** `npm run dev` (Vite, :5173) + `vite.config.ts` proxy: `/api` ve `/ws` → `localhost:8765`

## LAN Erişimi
- FastAPI `host="0.0.0.0"` ile başlatılırsa telefon tarayıcısından `http://<pc-ip>:8765` erişimi
- Windows Firewall'da 8765/TCP gelen kuralı gerekir (yalnız Private profil önerilir)
- Token auth zorunlu olduğundan LAN'da açık olması kabul edilebilir risk; internete port yönlendirme **yapılmaz** (uzak erişim Faz 5'te Tailscale/Cloudflare Tunnel)
