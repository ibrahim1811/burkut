"""
BÜRKÜT AI Sohbet Penceresi — widget üzerinden PC'de AI ile konuşma.
"""

import asyncio
import threading
import uuid
import re
import datetime
import os
import tempfile
import tkinter as tk
import customtkinter as ctk
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Renk paleti ──────────────────────────────────────────────────────────────
BG       = "#0d1117"
BG_CARD  = "#161b22"
BG_INPUT = "#1c2128"
BG_CODE  = "#1a1d27"
BORDER   = "#30363d"
ACCENT   = "#e2b96a"
T1       = "#f0f6fc"
T2       = "#8b949e"
C_USER   = "#79c0ff"
C_AI     = "#3fb950"
C_CODE   = "#e2b96a"
C_ERR    = "#ff7b72"
C_ACT    = "#d2a8ff"


def _parse_segments(text: str) -> list:
    """Metni (tip, içerik) listesine böl: 'text' veya 'code'."""
    segs = []
    last = 0
    for m in re.finditer(r"```(?:\w+)?\n?(.*?)```", text, re.DOTALL):
        before = text[last:m.start()].strip()
        if before:
            segs.append(("text", before))
        code = m.group(1).rstrip()
        if code:
            segs.append(("code", code))
        last = m.end()
    tail = text[last:].strip()
    if tail:
        segs.append(("text", tail))
    return segs or [("text", text)]


class AIChatWindow(ctk.CTkToplevel):
    """Singleton sohbet penceresi — get_or_create() ile aç."""

    _instance = None

    @classmethod
    def get_or_create(cls, parent):
        if cls._instance is None or not cls._instance.winfo_exists():
            cls._instance = cls(parent)
        else:
            cls._instance.deiconify()
            cls._instance.lift()
            cls._instance.focus_force()
        return cls._instance

    def __init__(self, parent):
        super().__init__(parent)
        ctk.set_appearance_mode("dark")

        self.title("Bürküt AI")
        self.geometry("500x660")
        self.minsize(380, 440)
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)

        self._session_id = str(uuid.uuid4())
        self._thinking   = False
        self._img_refs   = []
        self._tmp_files  = []   # geçici ekran görüntüsü dosyaları

        # Arka plan asyncio loop
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.after(400, self._greet)

    # ════════════════════════════════════════════════════════════════
    # Arayüz inşası
    # ════════════════════════════════════════════════════════════════

    def _build_ui(self):
        # ── 1. BAŞLIK ÇUBUĞU (üst, sabit)
        bar = tk.Frame(self, bg=BG_CARD, height=42)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar, text="🦅  Bürküt AI",
            bg=BG_CARD, fg=ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=12, pady=0)

        self._status_lbl = tk.Label(
            bar, text="● hazır",
            bg=BG_CARD, fg=C_AI,
            font=("Segoe UI", 8),
        )
        self._status_lbl.pack(side="left", padx=4)

        _btn = dict(
            bg=BG_CARD, fg=T2,
            font=("Segoe UI", 12), relief="flat",
            cursor="hand2", bd=0,
            activebackground="#21262d", activeforeground=T1,
            padx=7, pady=6,
        )
        tk.Button(bar, text="✕", command=self.withdraw,  **_btn).pack(side="right", padx=2)
        tk.Button(bar, text="🗑", command=self._clear,    **_btn).pack(side="right")
        tk.Button(bar, text="📌", command=self._pin,      **_btn).pack(side="right")

        # ── 2. GİRİŞ ALANI (alt, sabit) — ÖNCE PACK ET!
        bottom = tk.Frame(self, bg=BG_CARD)
        bottom.pack(side="bottom", fill="x")

        # Input kutusu
        input_wrap = tk.Frame(bottom, bg=BORDER, bd=1)
        input_wrap.pack(fill="x", padx=10, pady=(10, 4))

        self._input = tk.Text(
            input_wrap,
            bg=BG_INPUT, fg=T1,
            font=("Segoe UI", 11),
            wrap="word",
            relief="flat",
            highlightthickness=0,
            insertbackground=T1,
            height=3,
            padx=10, pady=8,
            selectbackground="#1c3a5e",
            selectforeground=T1,
        )
        self._input.pack(fill="x")
        self._input.bind("<Return>",         self._on_enter)
        self._input.bind("<Shift-Return>",   lambda e: None)
        self._input.bind("<Control-Return>", lambda e: self._do_send() or "break")
        self._input.focus_set()

        # Gönder satırı
        send_row = tk.Frame(bottom, bg=BG_CARD)
        send_row.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(
            send_row,
            text="Enter ↵ gönder  •  Shift+Enter yeni satır",
            bg=BG_CARD, fg=T2, font=("Segoe UI", 8),
        ).pack(side="left")

        self._send_btn = tk.Button(
            send_row,
            text="Gönder  ↵",
            bg=ACCENT, fg="#0d1117",
            font=("Segoe UI", 9, "bold"),
            relief="flat", cursor="hand2",
            padx=14, pady=5,
            activebackground="#c9a050", activeforeground="#0d1117",
            command=self._do_send,
        )
        self._send_btn.pack(side="right")

        # ── 3. AYIRICI
        tk.Frame(self, bg=BORDER, height=1).pack(side="bottom", fill="x")

        # ── 4. MESAJ ALANI (ortada, genişler)
        chat_wrap = tk.Frame(self, bg=BG)
        chat_wrap.pack(side="top", fill="both", expand=True)

        self._chat = tk.Text(
            chat_wrap,
            bg=BG, fg=T1,
            font=("Segoe UI", 11),
            state="disabled",
            wrap="word",
            relief="flat",
            highlightthickness=0,
            cursor="arrow",
            selectbackground="#1c3a5e",
            selectforeground=T1,
            padx=12, pady=10,
            spacing1=2, spacing3=6,
        )
        vsb = tk.Scrollbar(
            chat_wrap, command=self._chat.yview,
            bg=BG_CARD, troughcolor=BG,
            activebackground=BORDER,
            width=8, bd=0, highlightthickness=0,
        )
        self._chat.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._chat.pack(side="left", fill="both", expand=True)

        # Tag tanımları
        self._chat.tag_configure("user_lbl",  foreground=C_USER,  font=("Segoe UI", 9, "bold"))
        self._chat.tag_configure("ai_lbl",    foreground=C_AI,    font=("Segoe UI", 9, "bold"))
        self._chat.tag_configure("time_tag",  foreground=T2,      font=("Segoe UI", 8))
        self._chat.tag_configure("user_msg",  foreground=T1,      font=("Segoe UI", 11))
        self._chat.tag_configure("ai_msg",    foreground=T1,      font=("Segoe UI", 11))
        self._chat.tag_configure("code_tag",  foreground=C_CODE,  font=("Consolas", 10),
                                  background=BG_CODE, lmargin1=16, lmargin2=16, rmargin=8)
        self._chat.tag_configure("action_tag", foreground=C_ACT,  font=("Segoe UI", 10))
        self._chat.tag_configure("err_tag",   foreground=C_ERR,   font=("Segoe UI", 11))

    # ════════════════════════════════════════════════════════════════
    # Yardımcı metodlar
    # ════════════════════════════════════════════════════════════════

    def _pin(self):
        cur = bool(self.attributes("-topmost"))
        self.attributes("-topmost", not cur)

    def _set_status(self, text: str, color: str = T2):
        self.after(0, lambda: self._status_lbl.configure(text=text, fg=color))

    def _set_thinking(self, on: bool):
        self._thinking = on
        if on:
            self._set_status("● düşünüyor...", "#f0a030")
            self.after(0, lambda: self._send_btn.configure(state="disabled", bg="#444", fg=T2))
        else:
            self._set_status("● hazır", C_AI)
            self.after(0, lambda: self._send_btn.configure(state="normal", bg=ACCENT, fg="#0d1117"))

    # ── Mesaj ekleme ──────────────────────────────────────────────────

    def _append(
        self,
        label: str, label_tag: str,
        text: str,  msg_tag: str,
        action_lines: list = None,
    ):
        now = datetime.datetime.now().strftime("%H:%M")

        def _do():
            self._chat.configure(state="normal")
            self._chat.insert("end", "\n")
            self._chat.insert("end", f"  {label}  ", label_tag)
            self._chat.insert("end", f"{now}\n", "time_tag")

            for seg_type, seg_text in _parse_segments(text):
                tag = "code_tag" if seg_type == "code" else msg_tag
                self._chat.insert("end", f"  {seg_text}\n", tag)

            if action_lines:
                for line in action_lines:
                    if line and line.strip():
                        self._chat.insert("end", f"  ⚙ {line.strip()[:200]}\n", "action_tag")

            self._chat.configure(state="disabled")
            self._chat.see("end")

        self.after(0, _do)

    def _append_image(self, img_bytes: bytes):
        """Ekran görüntüsünü chat'e thumbnail olarak ekle."""
        try:
            from PIL import Image
            import io as _io
            import base64

            full = Image.open(_io.BytesIO(img_bytes))
            max_w = 430
            r = min(1.0, max_w / full.width)
            thumb = full.resize((int(full.width * r), int(full.height * r)), Image.LANCZOS)

            # Tam boyutu geçici dosyaya kaydet (tıklanınca açılır)
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix="burkut_")
            full.save(tmp.name, quality=92)
            tmp.close()
            self._tmp_files.append(tmp.name)  # temizlik için takip et

            # tk.PhotoImage base64 PNG bekler
            buf = _io.BytesIO()
            thumb.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            photo = tk.PhotoImage(data=b64)
            self._img_refs.append(photo)

            def _insert(ph=photo, path=tmp.name):
                self._chat.configure(state="normal")
                lbl = tk.Label(self._chat, image=ph, bg=BG, cursor="hand2")
                lbl.bind("<Button-1>", lambda e: os.startfile(path))
                self._chat.window_create("end", window=lbl, padx=12, pady=6)
                self._chat.insert("end", "\n")
                self._chat.configure(state="disabled")
                self._chat.see("end")

            self.after(0, _insert)
        except Exception as e:
            self._append("", "ai_lbl", f"(Görüntü gösterilemedi: {e})", "err_tag")

    # ── Karşılama ─────────────────────────────────────────────────────

    def _greet(self):
        from ai.brain import is_ollama_available, get_available_models
        if is_ollama_available():
            models = get_available_models()
            model_str = models[0] if models else "yükleniyor..."
            msg = (
                f"Merhaba! Ben Bürküt 🦅   (model: {model_str})\n\n"
                "Ne yapmamı istersin? Örneğin:\n"
                "• Ekran görüntüsü al\n"
                "• Chrome'u aç ve YouTube'a git\n"
                "• Python ile merhaba dünya yaz\n"
                "• Hava durumu nedir?\n"
                "• https://... analiz et"
            )
        else:
            msg = (
                "⚠️ Ollama çalışmıyor!\n\n"
                "Bir terminalde şunu çalıştır:\n"
                "    ollama serve\n\n"
                "Sonra buradan konuşabilirsin."
            )
        self._append("Bürküt", "ai_lbl", msg, "ai_msg")

    def _clear(self):
        from ai.memory import clear_session
        clear_session(self._session_id)
        self._session_id = str(uuid.uuid4())
        self._chat.configure(state="normal")
        self._chat.delete("1.0", "end")
        self._chat.configure(state="disabled")
        self._img_refs.clear()
        for f in self._tmp_files:
            try:
                os.unlink(f)
            except Exception:
                pass
        self._tmp_files.clear()
        self._greet()

    # ── Gönderme ──────────────────────────────────────────────────────

    def _on_enter(self, event):
        if event.state & 0x1:   # Shift basılı → normal newline
            return None
        self._do_send()
        return "break"

    def _do_send(self, *_):
        if self._thinking:
            return
        text = self._input.get("1.0", "end").strip()
        if not text:
            return
        self._input.delete("1.0", "end")
        self._append("Kayra", "user_lbl", text, "user_msg")
        self._set_thinking(True)

        asyncio.run_coroutine_threadsafe(
            self._run_ai(text), self._loop
        ).add_done_callback(self._on_done)

    async def _run_ai(self, text: str):
        from ai.brain import BurkutBrain
        return await BurkutBrain(self._session_id).chat(text, chat_id=0)

    def _on_done(self, future):
        try:
            text_resp, actions, images = future.result()
        except Exception as e:
            self._append("Hata", "ai_lbl", str(e), "err_tag")
            self._set_thinking(False)
            return

        self._append("Bürküt", "ai_lbl", text_resp, "ai_msg", action_lines=actions)
        for img in images:
            self._append_image(img)
        self._set_thinking(False)
