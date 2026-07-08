# 07 — Güvenlik

## Mevcut Durum (Tespit)
- ❗ `config.json` içinde **gerçek Telegram bot token commit'li** ve git geçmişinde mevcut (GitHub'a push edilmiş)
- `.env` diskte var ve git-ignored, ancak aynı sırların config.json kopyası sızmış durumda
- Relay `X-Agent-Token` ile korunuyor (iyi); Telegram tarafında `authorized_users` + rate limit var (iyi)

## Acil Plan (Faz 1 başında, kod yazmadan önce)
1. **Sır taşıma:** `config.json`'daki tüm sırlar `.env`'e (`TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `AGENT_TOKEN`, yeni `BURKUT_API_TOKEN`). `utils/config_manager.py` zaten env fallback destekliyor.
2. **Şablonlaştırma:** `config.example.json` (sırsız) repoya girer; gerçek `config.json` `.gitignore`'a eklenir ve git index'ten çıkarılır (`git rm --cached config.json`).
3. **Token rotasyonu (ertelenemez):**
   - Telegram: BotFather → `/revoke` → yeni token
   - Groq: console.groq.com → key sil, yenisini üret
   - `AGENT_TOKEN`: yeni rastgele değer üret
   - ⚠️ **Eşzamanlılık uyarısı:** Yeni değerler Render env vars ve yerel `.env`'e **aynı anda** girilmeli, aksi halde relay/bot kopar. Sıra: Render env güncelle → deploy → yerel `.env` güncelle → agent restart.
4. **Geçmiş temizliği (Faz 2c'ye ertelendi):** `git filter-repo` ile config.json geçmişten silinir + force push. Rotasyon yapıldığı sürece eski token değersizdir; bu adım kozmetik ama yapılacak.

## API Katmanı Güvenliği (server/)
- **Auth:** Tüm `/api/*` ve `/ws` istekleri `X-Burkut-Token` header (WS'de `?token=`) ister; `.env`'deki `BURKUT_API_TOKEN` ile sabit-zaman karşılaştırma (`hmac.compare_digest`)
- **Bind:** Varsayılan `127.0.0.1`; LAN erişimi bilinçli olarak `0.0.0.0` + firewall kuralıyla açılır
- **Rate limit:** Mevcut `utils/security.py` deseni FastAPI middleware'e uyarlanır (IP+endpoint bazlı, kayan pencere)
- **CORS:** Tek origin (static mount) sayesinde kapalı; dev'de yalnız `localhost:5173`'e izin

## Audit Log
`audit_log` tablosu (bkz. 03-database.md): `ts, actor (telegram:<id>|dashboard|voice|automation:<id>), channel, action, params JSON, success, result`.
- Faz 1: server/ endpoint'leri yazar
- Faz 2c: Telegram handler'ları ve voice pipeline'ı da aynı tabloya bağlanır (tek görünürlük noktası)
- Dashboard'da salt-okunur "Audit" görünümü (Faz 4)

## Gelecek (Faz 4+)
- **TOTP 2FA:** Kritik eylemler (güç kapatma, dosya silme, kod çalıştırma) için `pyotp` tabanlı tek kullanımlık kod onayı
- **Yetki seviyeleri:** read-only token (mobil widget) vs full token
- **Şifreleme:** `burkut.db` içinde hassas alanlar için alan-bazlı şifreleme (Fernet, key `.env`'de) — tam disk şifreleme kullanıcının BitLocker'ına bırakılır
- **Sır tarayıcı:** pre-commit hook ile `detect-secrets` benzeri basit regex taraması
