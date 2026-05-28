"""
BÜRKÜT Ana Widget — PySide6 frameless masaüstü widget.
"""
import sys
import datetime
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QSystemTrayIcon, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QSize
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QIcon, QBrush, QAction

from widget.widget_config import load_widget_config, save_position, save_widget_config
from widget.stats_panel import StatsPanel
from widget.voice_indicator import VoiceIndicator


BG      = "#0d1117"
BG_CARD = "#161b22"
BORDER  = "#30363d"
ACCENT  = "#e2b96a"
T1      = "#f0f6fc"
T2      = "#8b949e"

DAYS_TR   = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS_TR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _make_tray_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#e2b96a")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("#0d1117"))
    font = QFont("Arial", 28, QFont.Bold)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignCenter, "B")
    p.end()
    return QIcon(pix)


class BurkutWidget(QWidget):
    def __init__(self):
        super().__init__()
        cfg = load_widget_config()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("BÜRKÜT")

        self._always_on_top = cfg.get("always_on_top", False)
        if self._always_on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self._W = cfg.get("width", 280)
        self._drag_pos = None
        self._pulse_colors = ["#1a2a1a", "#1e3020", "#223825", "#1e3020", "#1a2a1a"]
        self._pulse_idx    = 0

        self._build_ui()
        self._setup_tray()

        # Position
        screen = QApplication.primaryScreen().geometry()
        px = cfg.get("position_x", screen.width() - self._W - 10)
        py = cfg.get("position_y", 20)
        self.move(px, py)

        # Timers
        QTimer.singleShot(0, self._fit_width)
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._update_clock)
        clock_timer.start(10_000)
        self._update_clock()

        pulse_timer = QTimer(self)
        pulse_timer.timeout.connect(self._pulse_ai_btn)
        pulse_timer.start(600)

        # Groq status check after 3s
        QTimer.singleShot(3000, self._check_groq_status)

        # Opacity
        self.setWindowOpacity(cfg.get("opacity", 0.95))

    def _fit_width(self):
        self.setFixedWidth(self._W)
        self.adjustSize()

    def _build_ui(self):
        self._container = QWidget(self)
        self._container.setObjectName("container")
        self._container.setStyleSheet(f"""
            #container {{
                background: {BG};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.addWidget(self._container)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(10, 10, 10, 6)
        layout.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(30)
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(4)

        title = QLabel("🦅  BÜRKÜT")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        hdr_layout.addWidget(title)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #3fb950; font-size: 9px;")
        hdr_layout.addWidget(self._dot)

        hdr_layout.addStretch()

        pin_btn = QPushButton("📌")
        pin_btn.setFixedSize(24, 24)
        pin_btn.setStyleSheet("background: transparent; border: none; font-size: 11px;")
        pin_btn.setToolTip("Her Zaman Üstte")
        pin_btn.clicked.connect(self._toggle_topmost)
        hdr_layout.addWidget(pin_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("background: transparent; border: none; color: #f0f6fc; font-size: 11px;")
        close_btn.clicked.connect(self.hide)
        hdr_layout.addWidget(close_btn)

        layout.addWidget(hdr)
        layout.addSpacing(6)

        # Clock
        self._clock_lbl = QLabel("00:00")
        self._clock_lbl.setStyleSheet(f"color: {T1}; font-size: 34px; font-weight: bold;")
        layout.addWidget(self._clock_lbl)

        self._date_lbl = QLabel("")
        self._date_lbl.setStyleSheet(f"color: {T2}; font-size: 10px;")
        layout.addWidget(self._date_lbl)

        layout.addSpacing(8)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(div1)
        layout.addSpacing(6)

        # Stats
        self._stats = StatsPanel()
        layout.addWidget(self._stats)

        layout.addSpacing(4)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(div2)
        layout.addSpacing(6)

        # AI Chat button
        self._ai_btn = QPushButton("🤖  Bürküt AI ile Konuş")
        self._ai_btn.setFixedHeight(34)
        self._ai_btn.setStyleSheet(f"""
            QPushButton {{
                background: #1a2a1a;
                border: 1px solid #2d4a2d;
                border-radius: 8px;
                color: #3fb950;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #253525; }}
        """)
        self._ai_btn.clicked.connect(self._open_ai_chat)
        layout.addWidget(self._ai_btn)
        layout.addSpacing(4)

        # Launcher label
        lbl = QLabel("HIZLI BAŞLAT")
        lbl.setStyleSheet(f"color: {T2}; font-size: 8px; font-weight: bold;")
        layout.addWidget(lbl)
        layout.addSpacing(2)

        # Launcher panel
        from widget.launcher_panel import LauncherPanel
        self._launcher = LauncherPanel(self._container, on_change=self.adjustSize, avail_w=self._W - 20)
        layout.addWidget(self._launcher)

        layout.addSpacing(4)

        # Voice indicator
        self._voice = VoiceIndicator()
        layout.addWidget(self._voice)

        # Set drag on header
        hdr.mousePressEvent   = self._drag_press
        hdr.mouseMoveEvent    = self._drag_move
        hdr.mouseReleaseEvent = self._drag_release

    def _drag_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _drag_move(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _drag_release(self, event):
        self._drag_pos = None
        save_position(self.x(), self.y())

    def _update_clock(self):
        now = datetime.datetime.now()
        self._clock_lbl.setText(now.strftime("%H:%M"))
        self._date_lbl.setText(f"{DAYS_TR[now.weekday()]}, {now.day} {MONTHS_TR[now.month]}")

    def _pulse_ai_btn(self):
        col = self._pulse_colors[self._pulse_idx % len(self._pulse_colors)]
        self._ai_btn.setStyleSheet(f"""
            QPushButton {{
                background: {col};
                border: 1px solid #2d4a2d;
                border-radius: 8px;
                color: #3fb950;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #253525; }}
        """)
        self._pulse_idx += 1

    def _check_groq_status(self):
        from ai.brain import is_groq_available
        if is_groq_available():
            self._dot.setStyleSheet("color: #3fb950; font-size: 9px;")
        else:
            self._dot.setStyleSheet("color: #ff7b72; font-size: 9px;")

    def _open_ai_chat(self):
        try:
            from widget.ai_chat import AIChatWindow
            AIChatWindow.get_or_create(self)
        except Exception as e:
            print(f"[Widget] AI chat açılamadı: {e}")

    def _toggle_topmost(self):
        self._always_on_top = not self._always_on_top
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._always_on_top)
        self.show()
        try:
            cfg = load_widget_config()
            cfg["always_on_top"] = self._always_on_top
            save_widget_config(cfg)
        except Exception:
            pass

    def _setup_tray(self):
        try:
            self._tray = QSystemTrayIcon(self)
            self._tray.setIcon(_make_tray_icon())
            self._tray.setToolTip("BÜRKÜT")

            menu = QMenu()
            menu.setStyleSheet("background: #161b22; color: #f0f6fc; border: 1px solid #30363d;")

            show_act = QAction("Göster", self)
            show_act.triggered.connect(self.show)
            menu.addAction(show_act)

            ai_act = QAction("🤖 Bürküt AI", self)
            ai_act.triggered.connect(self._open_ai_chat)
            menu.addAction(ai_act)

            hide_act = QAction("Gizle", self)
            hide_act.triggered.connect(self.hide)
            menu.addAction(hide_act)

            pin_act = QAction("Her Zaman Üstte", self)
            pin_act.triggered.connect(self._toggle_topmost)
            menu.addAction(pin_act)

            menu.addSeparator()

            quit_act = QAction("Çıkış", self)
            quit_act.triggered.connect(self._quit_app)
            menu.addAction(quit_act)

            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._tray_activated)
            self._tray.show()
        except Exception as e:
            print(f"[Widget] Tray hatası: {e}")

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit_app(self):
        try:
            self._stats.stop()
        except Exception:
            pass
        try:
            self._tray.hide()
        except Exception:
            pass
        QApplication.quit()

    def get_voice_indicator(self):
        return self._voice


def start_widget():
    app = QApplication.instance() or QApplication(sys.argv)
    widget = BurkutWidget()
    widget.show()
    return widget, app
