"""
Hızlı başlatıcı paneli.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QComboBox, QMenu, QSizePolicy,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QAction

from widget.widget_config import get_launchers, save_launchers, add_launcher


COLS    = 4
BTN_PAD = 3

EMOJIS = [
    "🌐","🔍","📧","💬","📱","💻","🖥️","⌨️",
    "🎵","🎬","📺","📷","🎙️","🎧","📻","🎤",
    "🎮","🎯","🎲","♟️","🏆","⚔️","🛡️","👾",
    "📁","📂","📝","📊","📈","📋","🗓️","📌",
    "⚙️","🔧","🔨","🛠️","🔑","🔒","💡","🔋",
    "🚀","⭐","🔥","💎","✨","🌟","⚡","🌈",
]

ADD_STYLE = """
    QPushButton {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        color: #8b949e;
        font-size: 22px;
    }
    QPushButton:hover { background: #1f2937; border-color: #e2b96a; }
"""


def _open_item(item: dict):
    import subprocess, webbrowser, os
    t    = item.get("type", "app")
    path = item.get("path", "")
    try:
        if t == "url":
            webbrowser.open(path)
        elif t == "folder":
            p = os.path.expanduser(path)
            os.startfile(p)
        else:
            subprocess.Popen(path, shell=True)
    except Exception as e:
        print(f"[Launcher] Açılamadı: {e}")


class _EmojiPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Emoji Seç")
        self.setModal(True)
        self.chosen = None
        layout = QGridLayout(self)
        layout.setSpacing(4)
        for i, em in enumerate(EMOJIS):
            btn = QPushButton(em)
            btn.setFixedSize(36, 36)
            btn.setStyleSheet("font-size: 18px; border: 1px solid #30363d; border-radius: 6px; background: #161b22;")
            btn.clicked.connect(lambda _, e=em: self._pick(e))
            layout.addWidget(btn, i // 8, i % 8)

    def _pick(self, em):
        self.chosen = em
        self.accept()


class _AddDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Ekle / Düzenle")
        self.setModal(True)
        self.setStyleSheet("background: #161b22; color: #f0f6fc;")
        self._result = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Icon row
        icon_row = QHBoxLayout()
        self._icon_btn = QPushButton(existing["icon"] if existing else "🚀")
        self._icon_btn.setFixedSize(40, 40)
        self._icon_btn.setStyleSheet("font-size: 20px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px;")
        self._icon_btn.clicked.connect(self._pick_emoji)
        icon_row.addWidget(QLabel("İkon:"))
        icon_row.addWidget(self._icon_btn)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        def _field(label, default=""):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(60)
            inp = QLineEdit(default)
            inp.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 4px; color: #f0f6fc;")
            row.addWidget(lbl)
            row.addWidget(inp)
            layout.addLayout(row)
            return inp

        self._name = _field("İsim:", existing["label"] if existing else "")
        self._path = _field("Yol:", existing["path"] if existing else "")

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Tür:"))
        self._type = QComboBox()
        self._type.addItems(["app", "url", "folder"])
        self._type.setCurrentText(existing["type"] if existing else "app")
        self._type.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #f0f6fc;")
        type_row.addWidget(self._type)
        layout.addLayout(type_row)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Kaydet")
        ok_btn.setStyleSheet("background: #238636; border-radius: 4px; padding: 6px; color: white;")
        ok_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("İptal")
        cancel_btn.setStyleSheet("background: #30363d; border-radius: 4px; padding: 6px; color: #f0f6fc;")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _pick_emoji(self):
        picker = _EmojiPicker(self)
        if picker.exec() == QDialog.Accepted and picker.chosen:
            self._icon_btn.setText(picker.chosen)

    def _save(self):
        name = self._name.text().strip()
        path = self._path.text().strip()
        if not name or not path:
            return
        self._result = {
            "label": name,
            "icon":  self._icon_btn.text(),
            "type":  self._type.currentText(),
            "path":  path,
        }
        self.accept()


class LauncherPanel(QWidget):
    def __init__(self, parent=None, on_change=None, avail_w=260, **kw):
        super().__init__(parent)
        self._on_change = on_change
        self._avail_w   = avail_w
        # Outer layout holds _inner widget
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QWidget()
        outer.addWidget(self._inner)
        self._refresh()

    def resize(self, avail_w: int):
        if avail_w != self._avail_w:
            self._avail_w = avail_w
            self._refresh()

    def _btn_size(self) -> int:
        bs = (self._avail_w - COLS * 2 * BTN_PAD) // COLS
        return max(52, min(115, bs))

    def _refresh(self):
        # _inner'ı tamamen yeni bir widget ile değiştir — eski layout'u sıfırlar
        outer_layout = self.layout()
        outer_layout.removeWidget(self._inner)
        self._inner.deleteLater()
        self._inner = QWidget()
        outer_layout.addWidget(self._inner)

        bs = self._btn_size()
        icon_sz = max(18, min(40, int(bs * 0.38)))

        grid = QGridLayout(self._inner)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(BTN_PAD)

        launchers = get_launchers()
        items = list(launchers) + [None]

        for idx, item in enumerate(items):
            row, col = divmod(idx, COLS)
            if item is None:
                btn = QPushButton("＋")
                btn.setFixedSize(bs, bs)
                btn.setStyleSheet(ADD_STYLE)
                btn.clicked.connect(self._add_item)
                grid.addWidget(btn, row, col)
            else:
                grid.addWidget(self._make_btn(item, bs, icon_sz), row, col)

        if self._on_change:
            QTimer.singleShot(60, self._on_change)

    def _make_btn(self, item: dict, bs: int, icon_sz: int) -> QWidget:
        """İkon büyük üstte, isim küçük altta — temiz kart butonu."""
        card = QWidget()
        card.setFixedSize(bs, bs)
        card.setStyleSheet("""
            QWidget {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 10px;
            }
            QWidget:hover {
                background: #1f2937;
                border-color: #e2b96a;
            }
        """)
        card.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(0)

        icon_lbl = QLabel(item.get("icon", "📄"))
        icon_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        icon_lbl.setStyleSheet(f"font-size: {icon_sz}px; background: transparent; border: none;")
        layout.addWidget(icon_lbl, 3)

        name = item.get("label", "")[:8]
        name_lbl = QLabel(name)
        name_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        name_lbl.setStyleSheet("font-size: 8px; color: #8b949e; background: transparent; border: none;")
        layout.addWidget(name_lbl, 1)

        # Tıklama ve sağ tık
        card.mousePressEvent = lambda e, i=item: (
            self._ctx_menu_card(e, i, card) if e.button() == Qt.RightButton
            else _open_item(i) if e.button() == Qt.LeftButton else None
        )
        return card

    def _ctx_menu_card(self, event, item: dict, card: QWidget):
        menu = QMenu(self)
        menu.setStyleSheet("background: #161b22; color: #f0f6fc; border: 1px solid #30363d;")
        edit_act   = menu.addAction("✏️ Düzenle")
        remove_act = menu.addAction("🗑️ Kaldır")
        action = menu.exec(event.globalPosition().toPoint())
        if action == edit_act:
            dlg = _AddDialog(self, existing=item)
            if dlg.exec() == QDialog.Accepted and dlg._result:
                launchers = get_launchers()
                for i, l in enumerate(launchers):
                    if l["label"] == item["label"] and l["path"] == item["path"]:
                        launchers[i] = dlg._result
                        break
                save_launchers(launchers)
                self._refresh()
        elif action == remove_act:
            launchers = [l for l in get_launchers()
                         if not (l["label"] == item["label"] and l["path"] == item["path"])]
            save_launchers(launchers)
            self._refresh()

    def _add_item(self):
        dlg = _AddDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg._result:
            add_launcher(dlg._result)
            self._refresh()

