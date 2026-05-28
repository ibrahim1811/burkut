"""
Ses asistanı durumu göstergesi.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont


class VoiceIndicator(QWidget):
    _state_signal = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._state_signal.connect(self._apply_state)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self._status = QLabel("🎙️ Ctrl+Space veya çift alkış → Konuş")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self._status)

        self._transcript = QLabel("")
        self._transcript.setAlignment(Qt.AlignCenter)
        self._transcript.setWordWrap(True)
        self._transcript.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        layout.addWidget(self._transcript)

    def _apply_state(self, action: str, text: str):
        if action == "listening":
            self._status.setStyleSheet("color: #e74c3c; font-size: 11px;")
            self._status.setText("🔴 Dinliyor...")
            self._transcript.setText("")
        elif action == "processing":
            self._status.setStyleSheet("color: #f39c12; font-size: 11px;")
            self._status.setText("⚙️ İşleniyor...")
        elif action == "transcript":
            self._transcript.setText(text)
        elif action == "done":
            self._status.setStyleSheet("color: #8b949e; font-size: 11px;")
            self._status.setText("🎙️ Ctrl+Space veya çift alkış → Konuş")
        elif action == "error":
            self._status.setStyleSheet("color: #e74c3c; font-size: 11px;")
            self._status.setText("❌ Hata")
            self._transcript.setText(text)
            QTimer.singleShot(3000, self._reset)
        elif action in ("loading", "ready"):
            self._status.setStyleSheet("color: #8b949e; font-size: 11px;")
            self._status.setText("🎙️ Ctrl+Space veya çift alkış → Konuş")

    def _reset(self):
        self._status.setStyleSheet("color: #8b949e; font-size: 11px;")
        self._status.setText("🎙️ Ctrl+Space veya çift alkış → Konuş")
        self._transcript.setText("")

    def notify(self, action: str, text: str = ""):
        self._state_signal.emit(action, text)
