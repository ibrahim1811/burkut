import sys
import customtkinter as ctk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from widget.widget_config import get_launchers, save_launchers, add_launcher

BG_CARD = "#161b22"
BG_HOV  = "#1f2937"
BORDER  = "#30363d"
T2      = "#8b949e"
ACCENT  = "#e2b96a"

COLS    = 4
BTN_PAD = 3   # her butonun etrafındaki boşluk (px)

EMOJIS = [
    "🌐", "🔍", "📧", "💬", "📱", "💻", "🖥️", "⌨️",
    "🎵", "🎬", "📺", "📷", "🎙️", "🎧", "📻", "🎤",
    "🎮", "🎯", "🎲", "♟️", "🏆", "⚔️", "🛡️", "👾",
    "📁", "📂", "📝", "📊", "📈", "📋", "🗓️", "📌",
    "⚙️", "🔧", "🔨", "🛠️", "🔑", "🔒", "💡", "🔋",
    "🚀", "⭐", "🔥", "💎", "✨", "🌟", "⚡", "🌈",
    "🛒", "💳", "💰", "🎁", "🍕", "☕", "🍔", "🛍️",
    "▶️", "⏩", "🎞️", "🎥", "📡", "🖼️", "🎨", "✏️",
    "🏠", "🏢", "🚗", "✈️", "🌍", "🗺️", "🏖️", "🏔️",
    "❤️", "💯", "🎉", "👍", "🤖", "🦅", "🐱", "🦊",
]


class LauncherPanel(ctk.CTkFrame):
    def __init__(self, master, on_change=None, avail_w=260, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_change = on_change
        self._avail_w   = avail_w
        self._ready     = False
        self._refresh()
        self._ready     = True

    def resize(self, avail_w: int):
        if avail_w != self._avail_w:
            self._avail_w = avail_w
            self._refresh()

    def _btn_size(self) -> int:
        # buton boyutu = mevcut genişliği 4 sütuna eşit böl (kenarlıklar çıkarılarak)
        bs = (self._avail_w - COLS * 2 * BTN_PAD) // COLS
        return max(52, min(115, bs))

    def _refresh(self):
        for w in self.winfo_children():
            w.destroy()

        bs      = self._btn_size()
        icon_sz = max(18, min(40, int(bs * 0.38)))
        name_sz = max(7,  min(11, bs // 7))

        launchers = get_launchers()
        items     = list(launchers) + [None]   # None = "+" slot

        row_frame = None
        for idx, item in enumerate(items):
            col = idx % COLS
            if col == 0:
                row_frame = ctk.CTkFrame(self, fg_color="transparent")
                row_frame.pack(fill="x", pady=(0, BTN_PAD))

            if item is None:
                ctk.CTkButton(
                    row_frame,
                    text="＋",
                    width=bs, height=bs,
                    fg_color=BG_CARD,
                    hover_color=BG_HOV,
                    text_color=T2,
                    font=ctk.CTkFont(size=max(16, bs // 3)),
                    corner_radius=12,
                    border_width=1,
                    border_color=BORDER,
                    command=self._show_add_dialog,
                ).pack(side="left", padx=BTN_PAD)
            else:
                card = ctk.CTkFrame(
                    row_frame,
                    width=bs, height=bs,
                    fg_color=BG_CARD,
                    corner_radius=12,
                    border_width=1,
                    border_color=BORDER,
                    cursor="hand2",
                )
                card.pack(side="left", padx=BTN_PAD)
                card.pack_propagate(False)

                icon_lbl = ctk.CTkLabel(
                    card, text=item.get("icon", "📄"),
                    font=ctk.CTkFont(size=icon_sz),
                )
                icon_lbl.place(relx=0.5, rely=0.38, anchor="center")

                name_lbl = ctk.CTkLabel(
                    card,
                    text=item.get("label", "")[:9],
                    font=ctk.CTkFont(size=name_sz),
                    text_color=T2,
                )
                name_lbl.place(relx=0.5, rely=0.82, anchor="center")

                def _click(e, i=idx):  self._launch(i)
                def _rclick(e, i=idx): self._show_context(i, e)
                def _enter(e, f=card): f.configure(fg_color=BG_HOV)
                def _leave(e, f=card): f.configure(fg_color=BG_CARD)

                for w in (card, icon_lbl, name_lbl):
                    w.bind("<Button-1>", _click)
                    w.bind("<Button-3>", _rclick)
                    w.bind("<Enter>",    _enter)
                    w.bind("<Leave>",    _leave)

        if self._ready and self._on_change:
            self.after(60, self._on_change)

    # ── Sağ tık menüsü ────────────────────────────────────────────
    def _show_context(self, idx: int, event):
        import tkinter as tk
        launchers = get_launchers()

        menu = tk.Menu(
            self.winfo_toplevel(), tearoff=0,
            bg="#1a1d27", fg="#f0f6fc",
            activebackground=BG_HOV, activeforeground="#f0f6fc",
            font=("Segoe UI", 10), bd=1, relief="flat",
        )

        if idx > 0:
            menu.add_command(label="◀  Geri Al",
                             command=lambda: self._move(idx, -1))
        if idx < len(launchers) - 1:
            menu.add_command(label="İleri Al  ▶",
                             command=lambda: self._move(idx, 1))
        menu.add_separator()
        menu.add_command(label="🗑  Sil",
                         foreground="#ff7b72", activeforeground="#ff7b72",
                         command=lambda: self._delete(idx))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _move(self, idx: int, direction: int):
        launchers = get_launchers()
        new_idx = idx + direction
        if 0 <= new_idx < len(launchers):
            launchers[idx], launchers[new_idx] = launchers[new_idx], launchers[idx]
            save_launchers(launchers)
            self._refresh()

    # ── Aç / Sil ──────────────────────────────────────────────────
    def _launch(self, idx: int):
        launchers = get_launchers()
        if idx >= len(launchers):
            return
        item = launchers[idx]
        t = item.get("type", "app")
        p = item.get("path", "")
        try:
            if   t == "app":    from core.launcher import open_app;        open_app(p)
            elif t == "url":    from core.launcher import open_url;        open_url(p)
            elif t == "folder": from core.launcher import open_folder;     open_folder(p)
            elif t == "file":   from core.launcher import open_file;       open_file(p)
            elif t == "steam":  from core.launcher import open_steam_game; open_steam_game(p)
        except Exception as e:
            print(f"[Launcher] Açılamadı: {e}")

    def _delete(self, idx: int):
        launchers = get_launchers()
        if idx >= len(launchers):
            return
        launchers.pop(idx)
        save_launchers(launchers)
        self._refresh()

    def _show_add_dialog(self):
        _AddDialog(self, self._refresh)


# ── Emoji Seçici ──────────────────────────────────────────────────
class _EmojiPicker(ctk.CTkToplevel):
    PICKER_COLS = 8

    def __init__(self, parent, on_select):
        super().__init__(parent)
        self.title("Emoji Seç")
        self.resizable(False, False)
        self.grab_set()
        self.focus_force()
        self._cb = on_select

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            width=self.PICKER_COLS * 44,
            height=min(len(EMOJIS) // self.PICKER_COLS * 44 + 10, 320),
        )
        scroll.pack(padx=6, pady=6)

        for c in range(self.PICKER_COLS):
            scroll.grid_columnconfigure(c, weight=1)

        for i, emoji in enumerate(EMOJIS):
            r, c = divmod(i, self.PICKER_COLS)
            ctk.CTkButton(
                scroll,
                text=emoji,
                width=36, height=36,
                font=ctk.CTkFont(size=18),
                fg_color="transparent",
                hover_color=BG_HOV,
                corner_radius=6,
                command=lambda e=emoji: self._pick(e),
            ).grid(row=r, column=c, padx=2, pady=2)

        self.geometry(f"+{parent.winfo_rootx()+20}+{parent.winfo_rooty()+20}")

    def _pick(self, emoji: str):
        self._cb(emoji)
        self.destroy()


# ── Kısayol Ekleme Diyaloğu ───────────────────────────────────────
class _AddDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self._cb = callback
        self.title("Kısayol Ekle")
        self.geometry("300x310")
        self.resizable(False, False)
        self.grab_set()
        self.focus_force()

        def _lbl(text):
            ctk.CTkLabel(self, text=text, anchor="w",
                         font=ctk.CTkFont(size=11),
                         ).pack(fill="x", padx=16, pady=(8, 2))

        _lbl("Etiket")
        self._lbl_e = ctk.CTkEntry(self, placeholder_text="Örn: Chrome")
        self._lbl_e.pack(fill="x", padx=16)

        _lbl("İkon")
        ico_row = ctk.CTkFrame(self, fg_color="transparent")
        ico_row.pack(fill="x", padx=16)

        self._ico_e = ctk.CTkEntry(ico_row, placeholder_text="🌐")
        self._ico_e.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            ico_row, text="Seç", width=46,
            fg_color=BG_CARD, hover_color=BG_HOV,
            font=ctk.CTkFont(size=10),
            command=self._open_picker,
        ).pack(side="right", padx=(6, 0))

        _lbl("Tür")
        self._type = ctk.CTkOptionMenu(
            self, values=["app", "url", "folder", "file", "steam"])
        self._type.pack(fill="x", padx=16)

        _lbl("Yol / URL / ID")
        self._path = ctk.CTkEntry(
            self, placeholder_text="chrome  /  https://…  /  730")
        self._path.pack(fill="x", padx=16)

        ctk.CTkButton(
            self, text="Ekle", command=self._save,
            fg_color=ACCENT, text_color="#0d1117", hover_color="#c9a050",
        ).pack(pady=14)

    def _open_picker(self):
        _EmojiPicker(self, self._set_icon)

    def _set_icon(self, emoji: str):
        self._ico_e.delete(0, "end")
        self._ico_e.insert(0, emoji)
        self.focus_force()

    def _save(self):
        label = self._lbl_e.get().strip()
        icon  = self._ico_e.get().strip() or "📄"
        type_ = self._type.get()
        path  = self._path.get().strip()
        if label and path:
            add_launcher(label, icon, type_, path)
            self._cb()
        self.destroy()
