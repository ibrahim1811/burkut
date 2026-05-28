import customtkinter as ctk
import queue


class VoiceIndicator(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(fg_color="transparent")
        self._queue: queue.Queue = queue.Queue()
        self._build_ui()
        self._poll()

    def _build_ui(self):
        self._status = ctk.CTkLabel(
            self,
            text="🎙️ Ctrl+Space → Konuş",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="center",
        )
        self._status.pack(fill="x", padx=8, pady=4)

        self._transcript = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#aaaaaa",
            anchor="center",
            wraplength=240,
        )
        self._transcript.pack(fill="x", padx=8, pady=(0, 4))

    def _poll(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                action = msg.get("action")
                if action == "listening":
                    self._status.configure(text="🔴 Dinliyor...", text_color="#e74c3c")
                    self._transcript.configure(text="")
                elif action == "processing":
                    self._status.configure(text="⚙️ İşleniyor...", text_color="#f39c12")
                elif action == "transcript":
                    self._transcript.configure(text=msg.get("text", ""))
                elif action == "done":
                    self._status.configure(text="🎙️ Ctrl+Space → Konuş", text_color="gray")
                elif action == "error":
                    self._status.configure(text="❌ Hata", text_color="#e74c3c")
                    self._transcript.configure(text=msg.get("text", ""))
                    self.after(3000, lambda: (
                        self._status.configure(text="🎙️ Ctrl+Space → Konuş", text_color="gray"),
                        self._transcript.configure(text=""),
                    ))
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def notify(self, action: str, text: str = ""):
        self._queue.put({"action": action, "text": text})
