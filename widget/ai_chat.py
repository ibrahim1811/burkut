"""
BÜRKÜT AI Sohbet Penceresi.
"""
import asyncio
import threading
import uuid
import re
import html as _html
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QSizePolicy, QScrollBar
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSize, QEvent
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor


BG       = "#0d1117"
BG_CARD  = "#161b22"
BG_INPUT = "#1c2128"
BORDER   = "#30363d"
ACCENT   = "#e2b96a"
T1       = "#f0f6fc"
T2       = "#8b949e"
C_USER   = "#79c0ff"
C_AI     = "#3fb950"


def _to_html(text: str) -> str:
    """Metni HTML'e çevir. Kod bloklarını <pre> ile sar. Tüm metin HTML-escape edilir."""
    parts = []
    last = 0
    for m in re.finditer(r"```(?:\w+)?\n?(.*?)```", text, re.DOTALL):
        before = text[last:m.start()].strip()
        if before:
            esc = _html.escape(before)
            parts.append(f"<p style='margin:2px 0; white-space:pre-wrap;'>{esc}</p>")
        code = _html.escape(m.group(1).rstrip())
        parts.append(
            f"<pre style='background:#1a1d27;border-radius:4px;padding:8px;"
            f"font-family:Consolas,monospace;font-size:10px;"
            f"color:#e2b96a;margin:4px 0;white-space:pre-wrap;'>{code}</pre>"
        )
        last = m.end()
    tail = text[last:].strip()
    if tail:
        esc = _html.escape(tail)
        parts.append(f"<p style='margin:2px 0; white-space:pre-wrap;'>{esc}</p>")
    return "".join(parts) or f"<p>{_html.escape(text)}</p>"


class _Signals(QObject):
    message_ready  = Signal(str, str, str)  # role, text, color
    thinking_done  = Signal()               # ana thread'de placeholder kaldır
    images_ready   = Signal(list)           # list of bytes — görseller


class AIChatWindow(QWidget):
    _instance = None

    @classmethod
    def get_or_create(cls, parent=None):
        # Silinmiş C++ nesnesine karşı koruma
        if cls._instance is not None:
            try:
                visible = cls._instance.isVisible()
            except RuntimeError:
                cls._instance = None

        if cls._instance is None:
            cls._instance = cls()
            cls._instance.show()
        elif not cls._instance.isVisible():
            cls._instance.show()
            cls._instance.raise_()
            cls._instance.activateWindow()
        else:
            cls._instance.raise_()
            cls._instance.activateWindow()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Bürküt AI")
        self.resize(500, 640)
        self.setMinimumSize(380, 440)

        self._session_id = str(uuid.uuid4())
        self._thinking   = False
        self._signals    = _Signals()
        self._signals.message_ready.connect(self._append_message)
        self._signals.thinking_done.connect(self._on_thinking_done)
        self._signals.images_ready.connect(self._on_images_ready)
        self._drag_pos   = None

        self._build_ui()
        self._greet()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet(f"""
            #container {{
                background: {BG};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        root.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {BG_CARD}; border-radius: 12px 12px 0 0;")
        header.mousePressEvent   = self._hdr_press
        header.mouseMoveEvent    = self._hdr_move
        header.mouseReleaseEvent = self._hdr_release
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 8, 0)

        title = QLabel("🤖  Bürküt AI")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        clear_btn = QPushButton("🗑")
        clear_btn.setFixedSize(26, 26)
        clear_btn.setStyleSheet(f"background: transparent; border: none; color: {T2}; font-size: 12px;")
        clear_btn.setToolTip("Geçmişi temizle")
        clear_btn.clicked.connect(self._clear_chat)
        h_layout.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("background: transparent; border: none; color: #f0f6fc; font-size: 11px;")
        close_btn.clicked.connect(self.hide)
        h_layout.addWidget(close_btn)

        layout.addWidget(header)

        # Chat area
        self._chat = QTextBrowser()
        self._chat.setOpenExternalLinks(True)
        self._chat.setStyleSheet(f"""
            QTextBrowser {{
                background: {BG};
                border: none;
                padding: 8px;
                color: {T1};
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QScrollBar:vertical {{
                background: {BG_CARD};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self._chat, 1)

        # Input area
        input_bar = QWidget()
        input_bar.setStyleSheet(f"background: {BG_CARD}; border-radius: 0 0 12px 12px;")
        inp_layout = QHBoxLayout(input_bar)
        inp_layout.setContentsMargins(8, 6, 8, 8)
        inp_layout.setSpacing(6)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Bir şeyler yazın... (Enter = gönder, Shift+Enter = yeni satır)")
        self._input.setFixedHeight(52)
        self._input.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_INPUT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px;
                color: {T1};
                font-size: 12px;
            }}
        """)
        self._input.installEventFilter(self)
        inp_layout.addWidget(self._input, 1)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(36, 36)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: #1a3a1a;
                border: 1px solid #2d4a2d;
                border-radius: 6px;
                color: #3fb950;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: #253525; }}
            QPushButton:disabled {{ background: #1a1a1a; color: #444; border-color: #333; }}
        """)
        self._send_btn.clicked.connect(self._send)
        inp_layout.addWidget(self._send_btn)

        layout.addWidget(input_bar)

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _hdr_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _hdr_move(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _hdr_release(self, event):
        self._drag_pos = None

    def _greet(self):
        from ai.brain import is_groq_available, get_available_models
        if is_groq_available():
            models = get_available_models()
            model = models[0] if models else "llama-3.3-70b-versatile"
            msg = f"Merhaba! Ben Bürküt AI, {model} modeliyle çalışıyorum. Nasıl yardımcı olabilirim?"
        else:
            msg = "⚠️ Groq API bağlantısı yok. GROQ_API_KEY değişkenini .env dosyasına ekleyin."
        self._append_message("ai", msg, C_AI)

    def _append_message(self, role: str, text: str, color: str):
        if role == "user":
            prefix = f"<div style='margin:6px 0;'><span style='color:{C_USER};font-weight:bold;font-size:11px;'>Sen</span><br>"
        else:
            prefix = f"<div style='margin:6px 0;'><span style='color:{color};font-weight:bold;font-size:11px;'>Bürküt</span><br>"

        body = _to_html(text)
        html = prefix + f"<span style='color:{color};'>{body}</span></div>"
        self._chat.append(html)

        sb = self._chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_thinking_done(self):
        # Ana thread'de çalışır — thinking placeholder'ı kaldır, butonu etkinleştir
        html = self._chat.toHtml()
        html = html.replace("⌛ Düşünüyor...", "")
        self._chat.setHtml(html)
        sb = self._chat.verticalScrollBar()
        sb.setValue(sb.maximum())
        self._send_btn.setEnabled(True)
        self._thinking = False

    def _on_images_ready(self, images: list):
        # Ana thread'de görselleri chat'e ekle
        import base64
        for img_bytes in images:
            try:
                b64 = base64.b64encode(img_bytes).decode()
                self._chat.append(
                    f"<div style='margin:4px 0;'>"
                    f"<img src='data:image/jpeg;base64,{b64}' "
                    f"style='max-width:100%;border-radius:4px;'/>"
                    f"</div>"
                )
            except Exception:
                self._chat.append("<p style='color:#8b949e;'>[📸 Görsel yüklenemedi]</p>")
        sb = self._chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or self._thinking:
            return
        self._input.clear()
        self._append_message("user", text, C_USER)
        self._thinking = True
        self._send_btn.setEnabled(False)
        self._append_message("ai", "⌛ Düşünüyor...", T2)
        threading.Thread(target=self._run_ai, args=(text,), daemon=True).start()

    def _run_ai(self, text: str):
        # Arka plan thread — Qt widget'larına DOĞRUDAN dokunmaz, sadece signal emit eder
        loop = asyncio.new_event_loop()
        try:
            from ai.brain import BurkutBrain
            brain = BurkutBrain(self._session_id)
            clean, actions, images = loop.run_until_complete(
                brain.chat(text, chat_id=0)
            )
            self._signals.thinking_done.emit()
            self._signals.message_ready.emit("ai", clean, C_AI)
            for act in actions:
                self._signals.message_ready.emit("action", act, "#d2a8ff")
            if images:
                self._signals.images_ready.emit(images)
        except Exception as e:
            self._signals.thinking_done.emit()
            self._signals.message_ready.emit("ai", f"❌ Hata: {e}", "#ff7b72")
        finally:
            loop.close()

    def _clear_chat(self):
        try:
            from ai.memory import clear_session
            clear_session(self._session_id)
        except Exception:
            pass
        self._chat.clear()
        self._session_id = str(uuid.uuid4())
        self._greet()
