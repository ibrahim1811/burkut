# BÜRKÜT OS — Product Requirements Document (PRD)

> Sürüm: 1.0 · Tarih: 2026-07-08 · Sahip: Kayra · Durum: Onaylandı (Faz 0)

## 1. Vizyon

Bürküt bir chatbot değildir. Bürküt; kullanıcısını tanıyan, alışkanlıklarını öğrenen, bilgisayarını yöneten, telefonuyla haberleşen, görevlerini takip eden ve gerektiğinde kendi önerilerini sunan, **sürekli çalışan kişisel bir AI işletim sistemidir**.

Mevcut PcBot (Telegram uzaktan kontrol + Groq beyni + ses asistanı + masaüstü widget) çalışan bir temel sunar. Bürküt OS, bu temeli **kırmadan** katman katman evriltir: gerçek bir Memory Engine, yerel bir API katmanı, canlı bir Dashboard ve zamanla Model Router, Automation Engine, Vision ve Plugin System.

**Yol gösterici ilkeler:**
- Tamamen kişisel: tek kullanıcı, tek sahip.
- Ücretsiz ağırlıklı: Groq free tier + yerel modeller; ücretli API'ler yalnızca opsiyonel.
- Evrim, devrim değil: çalışan hiçbir özellik bozulmaz; her faz geriye dönük uyumludur.
- Yerel öncelikli: hassas veri (bellek, ekran, dosyalar) PC'de kalır; bulut yalnızca relay.

## 2. Persona

| | |
|---|---|
| **Kullanıcı** | Kayra — tek ve yetkili kullanıcı |
| **Profil** | Öğrenci + geliştirici; Windows 11 masaüstü, Android telefon |
| **Kullanım** | Uzun bilgisayar seansları, kod projeleri, dersler/sınavlar, Telegram üzerinden uzaktan kontrol |
| **Beklenti** | "Jarvis hissi": doğal dille konuşma, PC'nin uzaktan tam kontrolü, kendisini hatırlayan bir asistan |

## 3. Kullanım Senaryoları

1. **Uzaktan durum:** Kayra dışarıdayken Telegram'dan `/durum` yazar; CPU/RAM/GPU/disk anlık raporu gelir.
2. **Doğal dil komut:** "Bürküt, Spotify'ı aç ve sesi %40 yap" — sesli veya Telegram'dan; `<EYLEM>` protokolüyle yürütülür.
3. **Hatırlama:** "Geçen hafta üzerinde çalıştığım proje neydi?" — Memory Engine semantik arama ile geçmiş konuşmalardan yanıt üretir.
4. **Kişisel bağlam:** "Yarın sınavım var demiştim, saat kaçtaydı?" — uzun süreli bellekteki kayıttan yanıtlar.
5. **Canlı izleme:** Tarayıcıda `localhost:8765` açılır; CPU/RAM/GPU grafikleri 2 sn'lik WebSocket akışıyla canlı akar.
6. **Bellek yönetimi:** Dashboard'un Bellek sayfasında "docker" araması yapılır; ilgili tüm anılar skorlanmış listelenir, düzenlenir veya silinir.
7. **Uzaktan dosya:** Telegram'dan "masaüstündeki rapor.pdf'i gönder" — dosya güvenlik filtrelerinden geçip Telegram'a düşer.
8. **Hatırlatıcı:** "Bürküt, 20 dakika sonra çayı hatırlat" — süre dolunca TTS + ekran overlay + Telegram bildirimi.
9. **Sesli diyalog:** "Bürküt" wake-word → Whisper STT → Groq NLU → edge-tts yanıtı; eller serbest kullanım.
10. **Ekran farkındalığı (Faz 3+):** "Ekrandaki hata ne?" — screenshot + OCR + LLM analizi ile açıklama.
11. **Otomasyon (Faz 2+):** "PC açılınca Spotify, Discord ve VSCode'u aç, bana günün görevlerini oku" — IFTTT tarzı kural olarak kaydedilir.
12. **Proaktif öneri (Faz 3+):** "4 saattir aralıksız bilgisayardasın, mola vermek ister misin?" — kullanım deseninden tetiklenen bildirim.
13. **Mobil kontrol (Faz 2d):** Android uygulamasından canlı PC durumu, dosya transferi ve AI sohbet.
14. **Uzaktan güç:** Telegram'dan "PC'yi 30 dakika sonra kapat" — zamanlanmış kapatma + iptal seçeneği.
15. **Öğrenme:** Bir URL gönderilir; Bürküt içeriği okur, key-facts çıkarır ve kalıcı belleğe işler — sonraki sorularda bağlam olarak kullanır.

## 4. Özellik Listesi (MoSCoW)

### Must (MVP — v0.x)
- Mevcut tüm PcBot yetenekleri regresyonsuz çalışır (Telegram 30+ komut, voice, widget, relay).
- Sır temizliği: token'lar `.env`'de, `config.json` şablonlaştırılmış, token'lar rotate edilmiş.
- SQLite veritabanı (`data/burkut.db`, WAL) + `memory.json` → SQLite migrasyonu.
- Memory Engine: embedding + FTS5 hybrid arama, ranking, token bütçeli context builder, `BurkutBrain` entegrasyonu.
- FastAPI yerel API katmanı (port 8765, token auth) + WebSocket canlı metrik.
- React Dashboard: Sistem (canlı grafikler), Bellek (arama/CRUD), Sohbet, Hatırlatıcılar.

### Should (v1.0)
- Model Router: Groq varsayılan, Ollama fallback, opsiyonel ücretli modeller; maliyet sayacı.
- Automation Engine: trigger/condition/action kuralları, dashboard'da kural editörü.
- Güvenlik sertleştirme: audit log tüm kanallarda, git geçmişi sır temizliği, rate-limit FastAPI'de.
- React Native Android uygulaması (canlı durum, dosya transferi, AI sohbet, FCM push).

### Could (v2.0)
- Vision/OCR: ekran analizi, "bu butona bas" tarzı UI otomasyonu.
- Plugin System: manifest + hook sözleşmesi; Spotify, Discord, OBS eklentileri.
- Proaktif AI: alışkanlık analizi, bağlamsal öneriler.
- 2FA (TOTP) kritik eylemler için; canlı ekran akışı.

### Won't (kapsam dışı)
- Çoklu kullanıcı / SaaS / genel dağıtım — Bürküt tek kişiliktir.
- iOS uygulaması.
- Kendi LLM eğitimi/fine-tune.
- Windows dışı masaüstü desteği (Linux/macOS agent).
- Ücretli altyapı zorunluluğu (her özellik ücretsiz katmanda çalışabilmeli).

## 5. Başarı Metrikleri

| Metrik | Hedef |
|---|---|
| Telegram komut regresyonu | 0 kırık komut (her faz sonunda smoke-test) |
| Bellek araması isabeti | Türkçe doğal dil sorgusunda ilgili anı ilk 3 sonuçta |
| Dashboard canlı veri gecikmesi | ≤ 2 sn |
| Bellek enjeksiyonu | Sohbette geçmiş bağlamın kendiliğinden kullanılması (manuel hatırlatma gerekmez) |
| Aylık işletme maliyeti | 0 TL (free tier'lar içinde) |
| Kurulum | Tek `.env` + `pip install` + `npm run build` ile temiz makinede ayağa kalkma |

## 6. Sürüm Hedefleri

| Sürüm | Kapsam | Faz karşılığı |
|---|---|---|
| **v0.1** | Dokümantasyon + sır temizliği + FastAPI iskelet + SQLite | Faz 0–1 |
| **v0.2** | Memory Engine tam çalışır (hybrid arama + brain entegrasyonu) | Faz 2 |
| **v0.3 (MVP)** | React Dashboard canlı; MVP çıkış kriterleri karşılandı | Faz 3 |
| **v1.0** | Model Router + Automation Engine + güvenlik sertleştirme + Android app | Faz 4 / 2a–2d |
| **v2.0** | Vision/OCR + Plugin System + Proaktif AI | Faz 3a–3c |

## 7. Kısıtlar ve Varsayımlar

- **Platform:** Windows 11, Python 3.11; Render free tier yalnızca Telegram bot + relay için.
- **Bütçe:** Ücretsiz ağırlıklı — Groq free tier, sentence-transformers (yerel), edge-tts, Vosk; ücretli API yalnızca kullanıcı anahtar girerse.
- **Donanım:** Embedding modeli ~470MB RAM; `BURKUT_EMBEDDINGS=off` ile FTS-only moda düşülebilir.
- **Ağ:** Dashboard varsayılan olarak yerel/LAN; internetten erişim Faz 2d'de (Cloudflare Tunnel / Tailscale) ele alınır.
