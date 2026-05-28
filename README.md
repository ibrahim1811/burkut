# 🦅 BÜRKÜT — Telegram PC Kontrol Botu

Telegram üzerinden PC'nizi uzaktan tam kontrol edin.

---

## Özellikler

- 🖥️ Gerçek zamanlı sistem izleme (CPU, RAM, disk, ağ)
- ⚡ Güç yönetimi (kapatma, yeniden başlatma, uyku, hazırda bekleme)
- 🔄 Süreç ve program kontrolü
- 📁 Dosya transferi (PC ↔ Telegram)
- 🔔 Akıllı bildirimler (boşta kalma, klasör izleme, program takibi)
- 🔒 Güvenlik sistemi (yetkili kullanıcı, onay mekanizması, path koruması)

---

## Kurulum

### 1. Gereksinimler

- Python 3.9 veya üzeri
- pip

### 2. Bağımlılıkları Kur

```bash
pip install -r requirements.txt
```

### 3. Bot Token Al

1. Telegram'da [@BotFather](https://t.me/BotFather) ile konuşun
2. `/newbot` komutunu gönderin
3. Bot adını ve kullanıcı adını belirleyin
4. Aldığınız token'ı kopyalayın

### 4. Telegram ID'nizi Bulun

1. [@userinfobot](https://t.me/userinfobot) ile konuşun
2. `/start` gönderin, size ID'nizi verecek

### 5. config.json Ayarla

```json
{
  "telegram_bot_token": "1234567890:AAAA-buraya-tokeninizi-yazin",
  "authorized_users": [123456789],
  "max_file_size_mb": 50,
  "allowed_download_paths": [
    "C:/Users/KULLANICI_ADINIZ/Downloads",
    "C:/Users/KULLANICI_ADINIZ/Documents",
    "C:/Users/KULLANICI_ADINIZ/Desktop"
  ],
  "blocked_file_extensions": [".exe", ".bat", ".cmd", ".msi", ".ps1", ".vbs", ".reg"],
  "auto_screenshot_quality": 85,
  "log_retention_days": 30,
  "quick_files": {
    "log": "C:/Users/KULLANICI_ADINIZ/PcBot/logs/app.log"
  }
}
```

### 6. Botu Başlat

```bash
python main.py
```

---

## Komut Listesi

### Sistem İzleme
| Komut | Açıklama |
|-------|----------|
| `/status` | CPU, RAM, disk, ağ, uptime raporu |
| `/screenshot` | Ekran görüntüsü al ve gönder |
| `/processes` | Çalışan süreçler (Top 10) |
| `/processes chrome` | Programa göre filtrele |
| `/network` | Ağ istatistikleri |

### Güç Yönetimi
| Komut | Açıklama |
|-------|----------|
| `/shutdown` | Hemen kapat (onay ister) |
| `/shutdown 30` | 30 dakika sonra kapat |
| `/shutdown 1h` | 1 saat sonra kapat |
| `/shutdown 2h30m` | 2 saat 30 dakika sonra kapat |
| `/restart [süre]` | Yeniden başlat |
| `/sleep` | Uyku moduna al |
| `/hibernate` | Hazırda beklet |
| `/cancel_shutdown` | Zamanlayıcıyı iptal et |
| `/shutdown_status` | Aktif zamanlayıcı bilgisi |

### Program Kontrolü
| Komut | Açıklama |
|-------|----------|
| `/programs` | Çalışan uygulamalar |
| `/kill chrome` | Programı zorla kapat |
| `/kill 1234` | PID ile kapat |
| `/run notepad` | Program başlat |

#### Desteklenen Kısayollar
`chrome`, `firefox`, `edge`, `notepad`, `spotify`, `discord`, `vscode`, `explorer`, `calc`, `paint`, `vlc`, `steam`, `telegram`, `word`, `excel`

### Dosya İşlemleri
| Komut | Açıklama |
|-------|----------|
| `/browse` | Varsayılan konumları göster |
| `/browse C:\Users\...\Downloads` | Klasöre göz at |
| `/download 5` | Browse'dan 5. dosyayı gönder |
| `/download C:\...\dosya.pdf` | Tam yol ile dosya gönder |
| `/search rapor.pdf` | Dosya ara |
| `/quicksend log` | Kısayol dosyası gönder |

**Dosya Yükleme:** Bota bir dosya gönderin, nereye kaydedeceğinizi soracak.

### Bildirimler
| Komut | Açıklama |
|-------|----------|
| `/notify Mesaj` | Anında hatırlatma |
| `/alert_when_idle 10` | 10 dk boşta kalırsa bildir |
| `/alert_when_process chrome.exe` | Program kapanırsa bildir |
| `/monitor_folder C:\...` | Klasöre yeni dosya eklenince bildir |
| `/stop_monitoring` | Tüm izlemeleri durdur |

---

## Güvenlik

- Yalnızca `authorized_users` listesindeki Telegram ID'leri botu kullanabilir
- Kapatma, yeniden başlatma, süreç kapatma işlemleri onay gerektirir
- Dosya indirme yalnızca `allowed_download_paths` içindeki konumlardan yapılabilir
- `.exe`, `.bat`, `.cmd` gibi tehlikeli uzantılar engellenir
- Path traversal (../../) saldırıları otomatik engellenir
- Tüm komutlar loglanır (`logs/app.log` ve `logs/activity.log`)

---

## Sorun Giderme

**Bot başlamıyor:**
- `config.json` dosyasının var olduğunu kontrol edin
- Bot token'ın doğru olduğundan emin olun
- İnternet bağlantısını kontrol edin

**Ekran görüntüsü alınamıyor:**
- `mss` ve `Pillow` kütüphanelerinin kurulu olduğunu kontrol edin: `pip install mss Pillow`

**Dosya gönderilemiyor:**
- Dosyanın `allowed_download_paths` içinde olduğundan emin olun
- Dosya boyutunun 50MB altında olduğunu kontrol edin

**Shutdown çalışmıyor:**
- Windows: Yönetici izinleriyle çalıştırın

---

## Güvenlik Uyarıları

> ⚠️ `config.json` ve `.env` dosyalarını **asla** GitHub'a yüklemeyin.
> Bu dosyalar `.gitignore` ile korunmaktadır.

> ⚠️ Botu yalnızca güvendiğiniz bir ortamda çalıştırın.
> Yetkili kullanıcılar PC üzerinde tam kontrole sahiptir.

---

## Lisans

MIT License — Kişisel kullanım için serbesttir.
