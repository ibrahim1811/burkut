"""
BÜRKÜT AI Beyni — Ollama/codellama entegrasyonu ile akıllı konuşma ve PC kontrolü.
"""

import io
import json
import re
import asyncio
import subprocess
import tempfile
import os
from typing import Optional, Tuple
import requests

from utils.logger import get_logger
from .memory import MemoryManager
from .web_reader import fetch_url, extract_github_raw, format_for_ai, detect_urls, python_summarize_url, extract_key_facts, format_result_summary
from .memory import save_learned, search_learned, get_learned_count

logger = get_logger()

# Telegram mesaj gönderici — main.py tarafından atanır
_telegram_sender = None


def set_telegram_sender(fn) -> None:
    global _telegram_sender
    _telegram_sender = fn


OLLAMA_BASE = "http://localhost:11434"
OLLAMA_CHAT = f"{OLLAMA_BASE}/api/chat"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"
MODEL = "mistral"

# ── Sistem prompt'u ────────────────────────────────────────────────────────────
# {datetime} her chat cagrısında anlık tarih/saatle doldurulur

SYSTEM_PROMPT = """Sen Burkut'sun. Kayra'nin kisisel yapay zeka asistanisin.
Kayra'nin PC'si: Windows 11, RTX 5070 Ti, 32GB RAM.
Bugun: {datetime}

Kisa, net, Turkce cevap ver. Etik uyarisi yazma. Ingilizce yazma.
Soru soruldugunda sadece yaz. Eylem gerektiginde <EYLEM> kullan.

PC eylemi icin: <EYLEM>{"action":"eylem","params":{...}}</EYLEM>

Eylem listesi:
open_app {"app":"chrome"} — uygulama ac
open_url {"url":"https://..."} — varsayilan tarayicida site ac
open_url_in {"browser":"opera","url":"..."} — belirli tarayicida ac
screenshot {} — ekran goruntusu al
system_status {} — CPU/RAM/GPU/disk durumu goster
mouse_move {"x":500,"y":300} — fareyi tasi
mouse_click {"x":500,"y":300,"button":"left"} — tikla (left/right/double)
type_text {"text":"..."} — klavyeyle yaz
key_press {"keys":["ctrl","c"]} — tus kombinasyonu
volume_set {"level":70} — ses seviyesi ayarla (0-100)
volume_up {"step":10} — sesi artir
volume_down {"step":10} — sesi kisalt
brightness_set {"level":80} — ekran parlakligini ayarla (0-100)
save_file {"path":"C:/...","content":"..."} — dosyaya yaz
run_python {"code":"..."} — Python kodu calistir
weather {"city":"Istanbul"} — hava durumu
news {"category":"genel"} — haberler
set_reminder {"text":"...","when":"30 dakika sonra"} — hatirlatici kur
list_reminders {} — hatirlaticlari listele
kill_process {"name":"chrome"} — sureci kapat
send_telegram {"message":"..."} — Telegram mesaji gonder
read_url {"url":"..."} — URL icerigini oku"""

# Mistral few-shot örnekleri — system prompt yerine gerçek mesaj geçmişi olarak eklenir
SEED_MESSAGES = [
    # Sohbet (eylem yok)
    {"role": "user", "content": "merhaba"},
    {"role": "assistant", "content": "Merhaba Kayra! Ne yapmani istersin?"},
    {"role": "user", "content": "tesekkurler"},
    {"role": "assistant", "content": "Rica ederim!"},
    # Uygulama/site acma
    {"role": "user", "content": "VLC ac"},
    {"role": "assistant", "content": "Aciyorum.\n<EYLEM>{\"action\":\"open_app\",\"params\":{\"app\":\"vlc\"}}</EYLEM>"},
    {"role": "user", "content": "Opera'da youtube'u ac"},
    {"role": "assistant", "content": "Aciyorum.\n<EYLEM>{\"action\":\"open_url_in\",\"params\":{\"browser\":\"opera\",\"url\":\"https://youtube.com\"}}</EYLEM>"},
    {"role": "user", "content": "Spotify ac"},
    {"role": "assistant", "content": "Aciyorum.\n<EYLEM>{\"action\":\"open_app\",\"params\":{\"app\":\"spotify\"}}</EYLEM>"},
    # Ekran goruntusu
    {"role": "user", "content": "Ekran goruntusu al"},
    {"role": "assistant", "content": "Aliyorum.\n<EYLEM>{\"action\":\"screenshot\",\"params\":{}}</EYLEM>"},
    # Sistem durumu
    {"role": "user", "content": "sistem durumu"},
    {"role": "assistant", "content": "Bakiyorum.\n<EYLEM>{\"action\":\"system_status\",\"params\":{}}</EYLEM>"},
    {"role": "user", "content": "CPU ve RAM ne durumda"},
    {"role": "assistant", "content": "Kontrol ediyorum.\n<EYLEM>{\"action\":\"system_status\",\"params\":{}}</EYLEM>"},
    # Ses kontrolu
    {"role": "user", "content": "sesi 70 yap"},
    {"role": "assistant", "content": "Ayarliyorum.\n<EYLEM>{\"action\":\"volume_set\",\"params\":{\"level\":70}}</EYLEM>"},
    {"role": "user", "content": "sesi artir"},
    {"role": "assistant", "content": "Artiriyorum.\n<EYLEM>{\"action\":\"volume_up\",\"params\":{\"step\":10}}</EYLEM>"},
    {"role": "user", "content": "sesi kisalt"},
    {"role": "assistant", "content": "Kisaltiyorum.\n<EYLEM>{\"action\":\"volume_down\",\"params\":{\"step\":10}}</EYLEM>"},
    # Parlaklik
    {"role": "user", "content": "parlaklik 80 yap"},
    {"role": "assistant", "content": "Ayarliyorum.\n<EYLEM>{\"action\":\"brightness_set\",\"params\":{\"level\":80}}</EYLEM>"},
    # Surec kapat
    {"role": "user", "content": "chrome'u kapat"},
    {"role": "assistant", "content": "Kapatiyorum.\n<EYLEM>{\"action\":\"kill_process\",\"params\":{\"name\":\"chrome\"}}</EYLEM>"},
    # Hava durumu
    {"role": "user", "content": "Izmir hava durumu"},
    {"role": "assistant", "content": "Bakiyorum.\n<EYLEM>{\"action\":\"weather\",\"params\":{\"city\":\"Izmir\"}}</EYLEM>"},
    # Telegram gonder
    {"role": "user", "content": "Telegramdan mesaj at: toplanti basliyor"},
    {"role": "assistant", "content": "Gonderiyorum.\n<EYLEM>{\"action\":\"send_telegram\",\"params\":{\"message\":\"Toplanti basliyor!\"}}</EYLEM>"},
    {"role": "user", "content": "Izmir hava durumunu Telegramdan gonder"},
    {"role": "assistant", "content": "Alip gonderiyorum.\n<EYLEM>{\"action\":\"weather\",\"params\":{\"city\":\"Izmir\"}}</EYLEM>\n<EYLEM>{\"action\":\"send_telegram\",\"params\":{\"message\":\"\"}}</EYLEM>"},
    # Ekran goruntusu + telegram
    {"role": "user", "content": "ekran goruntusu al ve telegramdan gonder"},
    {"role": "assistant", "content": "Alip gonderiyorum.\n<EYLEM>{\"action\":\"screenshot\",\"params\":{}}</EYLEM>\n<EYLEM>{\"action\":\"send_telegram\",\"params\":{\"message\":\"\"}}</EYLEM>"},
    # Hatirlatici
    {"role": "user", "content": "Hatirlatici kur: 30 dakika sonra kahve"},
    {"role": "assistant", "content": "Kuruyorum.\n<EYLEM>{\"action\":\"set_reminder\",\"params\":{\"text\":\"Kahve\",\"when\":\"30 dakika sonra\"}}</EYLEM>"},
    # Python
    {"role": "user", "content": "python ile 1'den 10'a kadar topla"},
    {"role": "assistant", "content": "Hesapliyorum.\n<EYLEM>{\"action\":\"run_python\",\"params\":{\"code\":\"print(sum(range(1,11)))\"}}</EYLEM>"},
    # URL oku
    {"role": "user", "content": "su siteyi oku: https://example.com"},
    {"role": "assistant", "content": "Okuyorum.\n<EYLEM>{\"action\":\"read_url\",\"params\":{\"url\":\"https://example.com\"}}</EYLEM>"},
]


# ── Ollama bağlantısı ──────────────────────────────────────────────────────────

def is_ollama_available() -> bool:
    try:
        r = requests.get(OLLAMA_TAGS, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_available_models() -> list:
    try:
        r = requests.get(OLLAMA_TAGS, timeout=5)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _call_ollama(messages: list, model: str = MODEL, timeout: int = 120) -> Optional[str]:
    """Senkron Ollama API çağrısı."""
    try:
        resp = requests.post(
            OLLAMA_CHAT,
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        logger.warning("Ollama API zaman aşımı")
        return None
    except Exception as e:
        logger.error(f"Ollama API hatası: {e}")
        return None


# ── Eylem ayrıştırma ──────────────────────────────────────────────────────────

def _parse_actions(text: str) -> Tuple[str, list]:
    """<EYLEM>...</EYLEM> bloklarını ayıkla. (temiz_metin, eylemler) döndür."""
    actions = []
    pattern = r"<EYLEM>(.*?)</EYLEM>"
    for match in re.finditer(pattern, text, re.DOTALL):
        raw = match.group(1).strip()
        try:
            action = json.loads(raw)
            actions.append(action)
        except json.JSONDecodeError:
            # JSON bozuksa düzeltmeye çalış
            try:
                # Tek tırnak → çift tırnak
                fixed = raw.replace("'", '"')
                action = json.loads(fixed)
                actions.append(action)
            except Exception:
                logger.warning(f"Eylem parse edilemedi: {raw[:100]}")

    clean = re.sub(pattern, "", text, flags=re.DOTALL).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean, actions


# ── Eylem çalıştırıcısı ───────────────────────────────────────────────────────

async def _execute_action(action: dict, chat_id: int) -> Tuple[str, Optional[bytes]]:
    """Eylemi çalıştır. (metin_sonucu, görüntü_bytes_veya_None) döndür."""
    name = action.get("action", "").strip()
    params = action.get("params", {})

    try:
        # Ekran görüntüsü
        if name == "screenshot":
            import mss
            from PIL import Image
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80, optimize=True)
            return "📸 Ekran görüntüsü alındı.", buf.getvalue()

        # Fare hareketi
        elif name == "mouse_move":
            from core.keyboard_mouse import move_mouse
            x, y = int(params["x"]), int(params["y"])
            move_mouse(x, y)
            return f"🖱️ Fare `({x}, {y})` konumuna taşındı.", None

        # Fare tıklama
        elif name == "mouse_click":
            from core.keyboard_mouse import click, double_click, right_click
            x, y = int(params["x"]), int(params["y"])
            btn = params.get("button", "left")
            if btn == "double":
                double_click(x, y)
                return f"🖱️ `({x}, {y})` çift tıklandı.", None
            elif btn == "right":
                right_click(x, y)
                return f"🖱️ `({x}, {y})` sağ tıklandı.", None
            else:
                click(x, y)
                return f"🖱️ `({x}, {y})` tıklandı.", None

        # Metin yazma
        elif name == "type_text":
            import pyperclip
            from core.keyboard_mouse import press_key
            text = params.get("text", "")
            pyperclip.copy(text)
            await asyncio.sleep(0.1)
            press_key("ctrl", "v")
            preview = text[:60] + ("..." if len(text) > 60 else "")
            return f"⌨️ Yazıldı: `{preview}`", None

        # Tuş kombinasyonu
        elif name == "key_press":
            from core.keyboard_mouse import press_key
            keys = params.get("keys", [])
            if keys:
                press_key(*keys)
            return f"⌨️ Tuş basıldı: `{'+'.join(keys)}`", None

        # Ses kontrolü
        elif name == "volume_set":
            from core.audio_controller import set_volume
            level = int(params.get("level", 50))
            new_level = set_volume(level)
            return f"🔊 Ses `%{new_level}` olarak ayarlandı.", None

        elif name == "volume_up":
            from core.audio_controller import volume_up
            step = int(params.get("step", 10))
            new_level = volume_up(step)
            return f"🔊 Ses artırıldı: `%{new_level}`", None

        elif name == "volume_down":
            from core.audio_controller import volume_down
            step = int(params.get("step", 10))
            new_level = volume_down(step)
            return f"🔉 Ses kısıldı: `%{new_level}`", None

        # Parlaklık
        elif name == "brightness_set":
            from core.display_manager import set_brightness
            level = int(params.get("level", 80))
            new_level = set_brightness(level)
            return f"☀️ Parlaklık `%{new_level}` olarak ayarlandı.", None

        # Uygulama açma
        elif name == "open_app":
            from core.launcher import open_app
            ok, msg = open_app(params.get("app", ""))
            return msg, None

        # URL açma (varsayılan tarayıcı)
        elif name == "open_url":
            from core.launcher import open_url
            ok, msg = open_url(params.get("url", ""))
            return msg, None

        # URL açma (belirli tarayıcı)
        elif name == "open_url_in":
            from core.launcher import open_url_in_browser
            ok, msg = open_url_in_browser(
                params.get("browser", "chrome"),
                params.get("url", "https://google.com"),
            )
            return msg, None

        # URL okuma
        elif name == "read_url":
            url = params.get("url", "")
            if "github.com" in url and "/blob/" in url:
                result = extract_github_raw(url)
            else:
                result = fetch_url(url)
            return format_for_ai(result, max_chars=3000), None

        # Dosya kaydetme
        elif name == "save_file":
            from pathlib import Path
            path = Path(params["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            content = params.get("content", "")
            path.write_text(content, encoding="utf-8")
            size = len(content.encode("utf-8"))
            return f"💾 Kaydedildi: `{path}` ({size:,} bayt)", None

        # Python çalıştırma
        elif name == "run_python":
            code = params.get("code", "")
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp = f.name

            try:
                _exec_loop = asyncio.get_running_loop()
                proc_result = await _exec_loop.run_in_executor(
                    None,
                    lambda t=tmp: subprocess.run(
                        ["python", t],
                        capture_output=True, text=True, timeout=30,
                    ),
                )
            finally:
                os.unlink(tmp)
            output = (proc_result.stdout or "") + (proc_result.stderr or "")
            output = output.strip() or "(çıktı yok)"
            icon = "✅" if proc_result.returncode == 0 else "❌"
            return f"{icon} Python çıktısı (kod {proc_result.returncode}):\n```\n{output[:2000]}\n```", None

        # Sistem durumu
        elif name == "system_status":
            from core.system_info import get_full_status
            return get_full_status(), None

        # Hava durumu
        elif name == "weather":
            from .news_weather import get_weather
            return get_weather(params.get("city", "Istanbul")), None

        # Haberler
        elif name == "news":
            from .news_weather import get_news
            return get_news(params.get("category", "genel")), None

        # Hatırlatıcı kur
        elif name == "set_reminder":
            from .calendar_mgr import add_calendar_event
            ok, msg = add_calendar_event(
                chat_id,
                params.get("text", "Hatırlatma"),
                params.get("when", "1 saat sonra"),
            )
            return msg, None

        # Hatırlatıcıları listele
        elif name == "list_reminders":
            from .calendar_mgr import get_reminders_text
            return get_reminders_text(chat_id), None

        # Süreç kapat
        elif name == "kill_process":
            from core.process_manager import kill_process
            name_proc = params.get("name", "")
            ok, msg = kill_process(name_proc)
            return msg, None

        # Telegram mesaj gönder
        elif name == "send_telegram":
            if _telegram_sender is None:
                return "❌ Telegram bağlantısı yok (bot çalışmıyor).", None
            message = params.get("message", "")
            if not message:
                return "❌ Gönderilecek mesaj boş.", None
            # Widget'tan çağrılırken chat_id=0 gelir; config'den owner al
            target = chat_id
            if target == 0:
                try:
                    from utils.config_manager import get_config
                    owners = get_config().get("authorized_users", [])
                    target = owners[0] if owners else 0
                except Exception:
                    pass
            if not target:
                return "❌ Telegram kullanıcı ID'si bulunamadı.", None
            _telegram_sender(target, message)
            return "✅ Telegram mesajı gönderildi.", None

        else:
            return f"⚠️ Bilinmeyen eylem: `{name}`", None

    except Exception as e:
        logger.error(f"Eylem hatası ({name}): {e}", exc_info=True)
        return f"❌ `{name}` eylemi başarısız: {e}", None


# ── URL ön işleme ─────────────────────────────────────────────────────────────

async def _preprocess_message(message: str) -> str:
    """Mesajdaki URL'leri önceden getir ve içeriği mesaja ekle."""
    urls = detect_urls(message)
    if not urls:
        return message

    additions = []
    loop = asyncio.get_running_loop()
    for url in urls[:2]:
        try:
            if "github.com" in url and "/blob/" in url:
                result = await loop.run_in_executor(None, extract_github_raw, url)
            else:
                result = await loop.run_in_executor(None, fetch_url, url)
            formatted = format_for_ai(result, max_chars=2500)
            additions.append(formatted)
        except Exception as e:
            logger.warning(f"URL ön getirme başarısız ({url}): {e}")

    if additions:
        return message + "\n\n--- Otomatik getirilen URL içerikleri ---\n" + "\n\n".join(additions)
    return message


# ── Ana BurkutBrain sınıfı ────────────────────────────────────────────────────

class BurkutBrain:
    def __init__(self, session_id: str, model: str = MODEL):
        self.session_id = session_id
        self.model = model
        self.memory = MemoryManager(session_id)

    async def chat(
        self,
        user_message: str,
        chat_id: int,
        prefetch_urls: bool = True,
    ) -> Tuple[str, list, list]:
        """
        Kullanıcı mesajını işle.
        Döndürür: (metin_yanıtı, eylem_sonuçları: list[str], görüntüler: list[bytes])
        """
        loop = asyncio.get_running_loop()

        # URL-only mesaj → Python ile doğrudan özetle, Ollama'ya gitme
        if prefetch_urls:
            urls = detect_urls(user_message)
            if urls:
                leftover = user_message
                for u in urls:
                    leftover = leftover.replace(u, "").strip()
                leftover_words = len(leftover.split()) if leftover else 0
                if leftover_words <= 4:
                    url = urls[0]
                    # Python ile oku + öğren
                    result = await loop.run_in_executor(None, fetch_url, url)
                    summary = format_result_summary(result) if result.get("type") != "error" else python_summarize_url(url)
                    # Hafızaya kaydet (öğrenme) — sadece başarılı fetch'ler için
                    if result.get("type") != "error":
                        facts = extract_key_facts(result)
                        _title = result.get("title", url)
                        _content = result.get("content", "")[:2000]
                        await loop.run_in_executor(
                            None,
                            lambda u=url, t=_title, c=_content, f=facts: save_learned(u, t, c, f)
                        )
                        learned_n = await loop.run_in_executor(None, get_learned_count)
                        summary += f"\n\n_📚 Hafızaya alındı. Toplam {learned_n} kaynak öğrenildi._"
                    self.memory.add("user", user_message)
                    self.memory.add("assistant", summary)
                    return summary, [], []

        # URL ön işleme (URL + soru olan mesajlar için)
        if prefetch_urls:
            enriched = await _preprocess_message(user_message)
        else:
            enriched = user_message

        # Konuşma geçmişini yükle
        history = self.memory.get_history(last_n=20)

        # Öğrenilmiş hafızada ilgili kaynak var mı?
        learned_ctx = ""
        try:
            related = await loop.run_in_executor(
                None, lambda: search_learned(user_message, max_results=2)
            )
            if related:
                parts = []
                for item in related:
                    parts.append(
                        f"[Hafiza: {item['title']} | {item['url']}] "
                        + " ".join(item.get("facts", [])[:5])
                    )
                learned_ctx = "\n".join(parts)
        except Exception:
            pass

        # Sistem promptuna anlık tarih/saat enjekte et
        from datetime import datetime as _dt
        now_str = _dt.now().strftime("%d %B %Y, %H:%M")
        system_content = SYSTEM_PROMPT.replace("{datetime}", now_str)

        # Mistral system rolünü görmezden geliyor; ilk user/assistant çifti olarak ekle
        messages = [
            {"role": "user",      "content": system_content},
            {"role": "assistant", "content": "Anladim. Burkut olarak hazir."},
        ]
        messages.extend(SEED_MESSAGES)
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})

        final_msg = enriched
        if learned_ctx:
            final_msg = f"{enriched}\n\n[Ilgili hafiza kayitlari:]\n{learned_ctx}"
        messages.append({"role": "user", "content": final_msg})

        # Kullanıcı mesajını orijinal haliyle kaydet
        self.memory.add("user", user_message)

        # Ollama çağrısı (bloklamayan)
        response = await loop.run_in_executor(
            None, lambda: _call_ollama(messages, self.model)
        )

        if response is None:
            models = get_available_models()
            if not models:
                fallback = (
                    "❌ Ollama çalışmıyor!\n\n"
                    "Lütfen bir terminalde şunu çalıştır:\n"
                    "`ollama serve`\n\n"
                    "Sonra modeli yükle:\n"
                    "`ollama pull mistral`"
                )
            else:
                fallback = (
                    f"❌ `{self.model}` modeli yanıt vermedi.\n\n"
                    f"Yüklü modeller: {', '.join(models)}\n"
                    f"Model değiştirmek için `/model <isim>` kullan."
                )
            return fallback, [], []

        # Eylemleri ayıkla
        clean_text, actions = _parse_actions(response)

        # Eylemleri sırayla çalıştır — send_telegram boşsa önceki sonucu enjekte et
        action_texts = []
        images = []
        prev_results: list[str] = []
        for act in actions:
            if act.get("action") == "send_telegram":
                msg = act.get("params", {}).get("message", "").strip()
                if not msg:
                    content = "\n".join(prev_results) if prev_results else user_message
                    act.setdefault("params", {})["message"] = content
            txt, img = await _execute_action(act, chat_id)
            action_texts.append(txt)
            prev_results.append(txt)
            if img:
                images.append(img)

        # Kullanıcı "telegram" dedi ama model send_telegram eylemi üretmediyse — otomatik gönder
        _tg_keywords = ("telegram", "telegramdan", "telegram'dan", "telegram üzerinden")
        user_lower = user_message.lower()
        has_tg_keyword = any(k in user_lower for k in _tg_keywords)
        has_tg_action  = any(a.get("action") == "send_telegram" for a in actions)
        if has_tg_keyword and not has_tg_action and prev_results and _telegram_sender:
            target = chat_id
            if target == 0:
                try:
                    from utils.config_manager import get_config
                    owners = get_config().get("authorized_users", [])
                    target = owners[0] if owners else 0
                except Exception:
                    pass
            if target:
                combined = "\n".join(prev_results)
                try:
                    _telegram_sender(target, combined)
                    action_texts.append("✅ Sonuç Telegram'a gönderildi.")
                except Exception as e:
                    action_texts.append(f"❌ Telegram gönderilemedi: {e}")

        # Yanıtı kaydet
        self.memory.add("assistant", clean_text)

        return clean_text, action_texts, images

    def set_model(self, model_name: str) -> bool:
        """Modeli değiştir. Başarı durumu döndür."""
        available = get_available_models()
        # Tam eşleşme veya prefix eşleşme
        match = next(
            (m for m in available if m == model_name or m.startswith(model_name + ":")),
            None,
        )
        if match:
            self.model = match
            return True
        # Yine de dene (model yoksa Ollama hata verir, biz loglarız)
        self.model = model_name
        return False

    def clear_history(self) -> None:
        self.memory.clear()


# ── Kod analiz yardımcısı ──────────────────────────────────────────────────────

async def analyze_code_file(
    file_path: str, session_id: str, chat_id: int
) -> Tuple[str, list, list]:
    """Bir kod dosyasını BÜRKÜT'e analiz ettir."""
    from pathlib import Path
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"❌ Dosya okunamadı: {e}", [], []

    ext = Path(file_path).suffix.lstrip(".")
    message = (
        f"Bu {ext} dosyasını analiz et, hataları bul ve iyileştirme öner:\n\n"
        f"**{file_path}**\n```{ext}\n{content[:5000]}\n```"
    )
    brain = BurkutBrain(session_id)
    return await brain.chat(message, chat_id, prefetch_urls=False)
