# Bürküt Jarvis v2 — Tasarım Dökümanı
_2026-06-24_

## Kapsam

Üç bağımsız geliştirme:
1. **Groq NLU Voice Pipeline** — sesli asistanı doğal dil anlayan Jarvis'e dönüştür
2. **Sesli Hatırlatıcı** — hatırlatma zamanı gelince TTS + ekran bildirimi
3. **Telegram → PC Overlay Bildirimi** — `/bildirim` komutuyla ekranda özel popup

---

## 1. Groq NLU Voice Pipeline

### Mevcut Durum
`voice_assistant.py` → STT → `command_parser.py` (regex) → sabit handler'lar.
Groq/brain.py sesli asistana bağlı değil. Hava durumu ve hatırlatıcı altyapısı var ama sese kapalı.

### Yeni Akış
```
Alt+Space → kayıt → STT → Groq NLU → intent + params → handler → TTS
```

### Groq NLU Prompt
`voice_assistant.py` içinde STT çıktısı şu system prompt ile Groq'a gönderilir:

```
Sen Bürküt'sün. Kullanıcının sesli komutunu analiz et ve JSON döndür:
{"intent": "...", "params": {...}}

Intent listesi:
- weather: {"city": "şehir adı, default Istanbul"}
- reminder_set: {"text": "ne hatırlatılacak", "when": "zaman ifadesi"}
- reminder_list: {}
- general: {"answer": "Türkçe kısa cevap"}
- system: {"cmd": "shutdown|restart|sleep|screenshot|status|volume_up|volume_down|mute|lock|..."}

Sadece JSON döndür, başka hiçbir şey yazma.
```

### Intent Handler'lar

| Intent | İşlem | TTS Çıktı |
|---|---|---|
| `weather` | `news_weather.get_weather(city)` → özet sat | "İstanbul'da 28 derece, parçalı bulutlu efendim." |
| `reminder_set` | `calendar_mgr.add_calendar_event(chat_id, text, when)` | "Tamam efendim, yarın sabah hatırlatırım." |
| `reminder_list` | `calendar_mgr.get_reminders_text()` → okunabilir liste | Her hatırlatmayı sırayla okur |
| `general` | Groq'un `answer` alanını doğrudan TTS'e ver | Cevabı sesli okur |
| `system` | Mevcut handler'lara yönlendir | Değişmez |

### Dosya Değişiklikleri
- `voice/voice_assistant.py` — `_on_stop()` içinde regex yerine `_groq_nlu(text)` çağrısı
- `voice/voice_assistant.py` — `_handle_intent(intent, params)` fonksiyonu eklenir
- `voice/command_parser.py` — system komutları için tutulur, NLU fallback olur

---

## 2. Sesli Hatırlatıcı

### Mevcut Durum
`calendar_mgr.py`'deki `_check_loop()` her 30 saniyede zamanı gelen hatırlatıcıları Telegram'a gönderir. TTS bağlantısı yok.

### Değişiklik
`calendar_mgr.py`'e ikinci bir callback eklenir: `_tts_callback`.

Hatırlatıcı tetiklenince:
1. `_tts_callback("Efendim, hatırlatmanız var: {text}")` — sesli uyarı
2. `_notify_callback(chat_id, text)` — Telegram bildirimi (mevcut)
3. `show_notification` action → PC overlay (Bölüm 3)

### Dosya Değişiklikleri
- `ai/calendar_mgr.py` — `set_tts_callback()` + `_tts_callback` çağrısı `_check_loop()`'a eklenir
- `voice/voice_assistant.py` — başlangıçta `calendar_mgr.set_tts_callback(text_to_speech.speak)` çağrısı

---

## 3. Telegram → PC Overlay Bildirimi

### Komut
```
/bildirim Bu mesajı göster
/bildirim 🚨 Acil toplantı 5 dakika sonra!
```

### Overlay Pencere
- `tkinter` tabanlı özel pencere (ek bağımlılık gerektirmez, Python built-in)
- Ekran ortasında, tüm pencerelerin üzerinde (`topmost=True`)
- Koyu arka plan, beyaz/sarı büyük metin, Bürküt logosu/ikonu
- 8 saniye sonra otomatik kapanır (veya kullanıcı tıklarsa)
- Thread içinde çalışır, ana akışı bloke etmez

### Akış
```
Telegram /bildirim [mesaj]
  → bot/handlers.py cmd_bildirim()
  → send_to_agent("show_notification", {"text": mesaj})
  → local/pc_agent.py _cmd_show_notification()
  → core/notifier.py show_overlay(text)  ← yeni dosya
```

### Dosya Değişiklikleri
- `core/notifier.py` — yeni, `show_overlay(text, duration=8)` fonksiyonu
- `local/pc_agent.py` — `_cmd_show_notification` handler + `_HANDLERS` kaydı
- `bot/handlers.py` — `cmd_bildirim()` async handler
- `main.py` — `/bildirim` CommandHandler kaydı

---

## Uygulama Sırası

1. `core/notifier.py` — overlay pencere (bağımsız, test edilebilir)
2. PC agent + Telegram handler — `/bildirim` uçtan uca
3. Groq NLU voice pipeline — `voice_assistant.py` refactor
4. Sesli hatırlatıcı — calendar_mgr TTS bağlantısı
