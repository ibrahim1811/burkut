import sys
import datetime
import threading
import customtkinter as ctk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from widget.widget_config import load_widget_config, save_position

# ── Renk paleti ───────────────────────────────────────────────────
BG      = "#0d1117"
BG_CARD = "#161b22"
BORDER  = "#30363d"
ACCENT  = "#e2b96a"
T1      = "#f0f6fc"
T2      = "#8b949e"
C_CPU   = "#58a6ff"
C_RAM   = "#3fb950"
C_GPU   = "#f78166"
C_VRAM  = "#d2a8ff"
C_DL    = "#79c0ff"
C_UL    = "#ff7b72"

DAYS_TR   = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS_TR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


class _StatCard(ctk.CTkFrame):
    def __init__(self, master, title: str, base_color: str, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, **kw)
        self._base = base_color

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=T2, anchor="w",
                     ).pack(fill="x", padx=8, pady=(7, 0))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(1, 0))

        self._val = ctk.CTkLabel(row, text="—",
                                 font=ctk.CTkFont(size=16, weight="bold"),
                                 text_color=T1, anchor="w")
        self._val.pack(side="left")

        self._sub = ctk.CTkLabel(row, text="",
                                 font=ctk.CTkFont(size=8), text_color=T2)
        self._sub.pack(side="right")

        self._bar = ctk.CTkProgressBar(self, height=3, corner_radius=2,
                                       fg_color="#21262d",
                                       progress_color=base_color)
        self._bar.set(0)
        self._bar.pack(fill="x", padx=8, pady=(2, 8))

    def update(self, val: str, pct: float, sub: str = ""):
        self._val.configure(text=val)
        self._sub.configure(text=sub)
        color = "#ff7b72" if pct > 85 else ("#f0a030" if pct > 70 else self._base)
        self._bar.configure(progress_color=color)
        self._bar.set(max(0.0, min(1.0, pct / 100)))


class BurkutWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        cfg = load_widget_config()
        self.title("")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.configure(fg_color=BG)

        self._always_on_top = cfg.get("always_on_top", False)
        self.attributes("-topmost", self._always_on_top)
        self.attributes("-alpha", cfg.get("opacity", 0.95))

        W = cfg.get("width", 280)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        px = cfg.get("position_x")
        py = cfg.get("position_y", 20)

        if px is None or not (-sw * 2 < px < sw * 3):
            px = sw - W - 10
        py = max(0, min(py, sh - 200))

        self._W = W
        self.geometry(f"{W}x10+{px}+{py}")

        self._build_ui()
        self._setup_drag()
        self._setup_tray()

        self.after(80, self._fit_height)
        self._start_stats()
        self._update_clock()

    # ── Auto-size ─────────────────────────────────────────────────
    def _fit_height(self):
        self.update_idletasks()
        try:
            h = self._outer.winfo_reqheight() + 4
            self.geometry(f"{self._W}x{h}+{self.winfo_x()}+{self.winfo_y()}")
        except Exception:
            pass

    # ── Build UI ──────────────────────────────────────────────────
    def _build_ui(self):
        self._outer = ctk.CTkFrame(
            self, fg_color=BG, corner_radius=14,
            border_width=1, border_color=BORDER,
        )
        self._outer.pack(fill="both", expand=True, padx=1, pady=1)

        # Header
        hdr = ctk.CTkFrame(self._outer, fg_color="transparent", height=36)
        hdr.pack(fill="x", padx=10, pady=(10, 0))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="🦅  BÜRKÜT",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=ACCENT).pack(side="left")
        self._online_dot = ctk.CTkLabel(
            hdr, text="●",
            font=ctk.CTkFont(size=9),
            text_color="#3fb950",
        )
        self._online_dot.pack(side="left", padx=(3, 0))
        self.after(3000, self._check_ollama_status)

        ctk.CTkButton(hdr, text="✕", width=24, height=24,
                      fg_color="transparent", hover_color="#7d1e1e",
                      font=ctk.CTkFont(size=11), corner_radius=6,
                      command=self._hide).pack(side="right")
        ctk.CTkButton(hdr, text="📌", width=24, height=24,
                      fg_color="transparent", hover_color=BG_CARD,
                      font=ctk.CTkFont(size=11), corner_radius=6,
                      command=self._toggle_topmost).pack(side="right", padx=(0, 2))

        # Clock
        self._clock = ctk.CTkLabel(
            self._outer, text="",
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=T1,
        )
        self._clock.pack(anchor="w", padx=13, pady=(8, 0))

        self._date = ctk.CTkLabel(
            self._outer, text="",
            font=ctk.CTkFont(size=10), text_color=T2,
        )
        self._date.pack(anchor="w", padx=15, pady=(0, 10))

        # Divider
        ctk.CTkFrame(self._outer, height=1, fg_color=BORDER,
                     corner_radius=0).pack(fill="x")

        # Stat cards 2×2
        sg = ctk.CTkFrame(self._outer, fg_color="transparent")
        sg.pack(fill="x", padx=10, pady=10)
        sg.columnconfigure((0, 1), weight=1, uniform="s")

        self._cc = _StatCard(sg, "CPU",  C_CPU)
        self._rc = _StatCard(sg, "RAM",  C_RAM)
        self._gc = _StatCard(sg, "GPU",  C_GPU)
        self._vc = _StatCard(sg, "VRAM", C_VRAM)

        self._cc.grid(row=0, column=0, padx=(0, 4), pady=(0, 5), sticky="nsew")
        self._rc.grid(row=0, column=1, padx=(4, 0), pady=(0, 5), sticky="nsew")
        self._gc.grid(row=1, column=0, padx=(0, 4), sticky="nsew")
        self._vc.grid(row=1, column=1, padx=(4, 0), sticky="nsew")

        # Network row
        net = ctk.CTkFrame(self._outer, fg_color=BG_CARD, corner_radius=8)
        net.pack(fill="x", padx=10, pady=(7, 4))

        ctk.CTkLabel(net, text="🌐",
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(8, 4), pady=6)

        self._dl = ctk.CTkLabel(net, text="↓ —",
                                font=ctk.CTkFont(size=10), text_color=C_DL)
        self._dl.pack(side="left", pady=6)

        self._ul = ctk.CTkLabel(net, text="↑ —",
                                font=ctk.CTkFont(size=10), text_color=C_UL)
        self._ul.pack(side="left", padx=(10, 0), pady=6)

        # Divider
        ctk.CTkFrame(self._outer, height=1, fg_color=BORDER,
                     corner_radius=0).pack(fill="x", pady=(6, 0))

        # AI Chat butonu
        self._ai_btn = ctk.CTkButton(
            self._outer,
            text="🤖  Bürküt AI ile Konuş",
            height=34,
            fg_color="#1a2a1a",
            hover_color="#253525",
            text_color="#3fb950",
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8,
            border_width=1,
            border_color="#2d4a2d",
            command=self._open_ai_chat,
        )
        self._ai_btn.pack(fill="x", padx=10, pady=(8, 4))
        self._ai_btn_pulse = False
        self._pulse_ai_btn()

        # Launcher
        ctk.CTkLabel(
            self._outer, text="HIZLI BAŞLAT",
            font=ctk.CTkFont(size=8, weight="bold"),
            text_color=T2,
        ).pack(anchor="w", padx=15, pady=(4, 4))

        from widget.launcher_panel import LauncherPanel
        self._launcher = LauncherPanel(
            self._outer, on_change=self._fit_height, avail_w=self._W - 20
        )
        self._launcher.pack(fill="x", padx=10, pady=(0, 6))

        # Resize grip — sürükle → widget genişler/daralır
        grip_bar = ctk.CTkFrame(self._outer, fg_color="transparent", height=14)
        grip_bar.pack(fill="x")
        grip_bar.pack_propagate(False)

        self._grip = ctk.CTkLabel(
            grip_bar, text="⠿ ⠿",
            font=ctk.CTkFont(size=9),
            text_color=BORDER,
            cursor="sb_h_double_arrow",
        )
        self._grip.pack(side="right", padx=8)

        self._rx = self._rw = 0

        def _gpress(e):
            self._rx, self._rw = e.x_root, self._W
            return "break"

        def _gdrag(e):
            nw = max(240, min(440, self._rw + e.x_root - self._rx))
            if nw != self._W:
                self._W = nw
                self.geometry(f"{nw}x{self.winfo_height()}+{self.winfo_x()}+{self.winfo_y()}")
                if hasattr(self, "_resize_after"):
                    self.after_cancel(self._resize_after)
                self._resize_after = self.after(130, self._do_resize)
            return "break"

        def _grelease(e):
            try:
                from widget.widget_config import load_widget_config, save_widget_config
                cfg = load_widget_config()
                cfg["width"] = self._W
                save_widget_config(cfg)
            except Exception:
                pass
            return "break"

        for _w in (grip_bar, self._grip):
            _w.bind("<ButtonPress-1>",   _gpress)
            _w.bind("<B1-Motion>",       _gdrag)
            _w.bind("<ButtonRelease-1>", _grelease)

    # ── Resize ────────────────────────────────────────────────────
    def _do_resize(self):
        try:
            self._launcher.resize(self._W - 20)
        except Exception:
            pass
        self._fit_height()

    # ── Clock ─────────────────────────────────────────────────────
    def _update_clock(self):
        now = datetime.datetime.now()
        self._clock.configure(text=now.strftime("%H:%M"))
        self._date.configure(
            text=f"{DAYS_TR[now.weekday()]}, {now.day} {MONTHS_TR[now.month]}"
        )
        self.after(10_000, self._update_clock)

    # ── Stats ─────────────────────────────────────────────────────
    def _start_stats(self):
        self._stop_ev = threading.Event()
        threading.Thread(target=self._stats_loop, daemon=True).start()

    def _stats_loop(self):
        import psutil
        try:
            import pynvml
            pynvml.nvmlInit()
            _gh = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_ok = True
        except Exception:
            gpu_ok = False

        prev_net = None

        while not self._stop_ev.is_set():
            try:
                cpu_pct = psutil.cpu_percent(interval=1)
                try:
                    f = psutil.cpu_freq()
                    freq_s = f"{f.current/1000:.1f}G" if f else ""
                except Exception:
                    freq_s = ""

                ram = psutil.virtual_memory()
                ram_s = f"{ram.used/1073741824:.1f}/{ram.total/1073741824:.0f}G"

                if gpu_ok:
                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(_gh)
                        mem  = pynvml.nvmlDeviceGetMemoryInfo(_gh)
                        temp = pynvml.nvmlDeviceGetTemperature(_gh, 0)
                        gpu_pct  = float(util.gpu)
                        vram_pct = mem.used / mem.total * 100
                        gpu_s    = f"{temp}°C"
                        vram_val = f"{mem.used/1073741824:.1f}G"
                        vram_s   = f"/{mem.total/1073741824:.0f}G"
                    except Exception:
                        gpu_pct = vram_pct = 0.0
                        gpu_s = ""; vram_val = "—"; vram_s = ""
                else:
                    gpu_pct = vram_pct = 0.0
                    gpu_s = "N/A"; vram_val = "—"; vram_s = ""

                curr_net = psutil.net_io_counters()
                if prev_net:
                    dl = (curr_net.bytes_recv - prev_net.bytes_recv) / 1048576
                    ul = (curr_net.bytes_sent - prev_net.bytes_sent) / 1048576
                    def _fmt(v):
                        if v < 0.1: return f"{v*1024:.0f}K/s"
                        if v < 10:  return f"{v:.1f}M/s"
                        return f"{v:.0f}M/s"
                    dl_s = f"↓ {_fmt(dl)}"
                    ul_s = f"↑ {_fmt(ul)}"
                else:
                    dl_s = "↓ —"; ul_s = "↑ —"
                prev_net = curr_net

                def _ui(
                    cpu_pct=cpu_pct, freq_s=freq_s,
                    ram=ram, ram_s=ram_s,
                    gpu_pct=gpu_pct, gpu_s=gpu_s,
                    vram_pct=vram_pct, vram_val=vram_val, vram_s=vram_s,
                    dl_s=dl_s, ul_s=ul_s,
                ):
                    if not self.winfo_exists():
                        return
                    try:
                        self._cc.update(f"{cpu_pct:.0f}%", cpu_pct, freq_s)
                        self._rc.update(f"{ram.percent:.0f}%", ram.percent, ram_s)
                        self._gc.update(
                            f"{gpu_pct:.0f}%" if gpu_pct > 0 or gpu_s != "N/A" else "—",
                            gpu_pct, gpu_s,
                        )
                        self._vc.update(vram_val, vram_pct, vram_s)
                        self._dl.configure(text=dl_s)
                        self._ul.configure(text=ul_s)
                    except Exception:
                        pass

                self.after(0, _ui)

            except Exception:
                import time; time.sleep(2)

    # ── Drag ──────────────────────────────────────────────────────
    def _setup_drag(self):
        self._dx = self._dy = 0

        def press(e):
            self._dx, self._dy = e.x_root, e.y_root

        def drag(e):
            x = self.winfo_x() + e.x_root - self._dx
            y = self.winfo_y() + e.y_root - self._dy
            self._dx, self._dy = e.x_root, e.y_root
            self.geometry(f"+{x}+{y}")

        def release(e): save_position(self.winfo_x(), self.winfo_y())

        self.bind("<ButtonPress-1>",   press)
        self.bind("<B1-Motion>",       drag)
        self.bind("<ButtonRelease-1>", release)

    # ── System tray ───────────────────────────────────────────────
    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill="#e2b96a")
            d.text((22, 16), "B", fill="#0d1117")
            menu = pystray.Menu(
                pystray.MenuItem("Göster",          self._show,            default=True),
                pystray.MenuItem("🤖 Bürküt AI",   lambda *_: self.after(0, self._open_ai_chat)),
                pystray.MenuItem("Gizle",           self._hide),
                pystray.MenuItem("Her Zaman Üstte", self._toggle_topmost),
                pystray.MenuItem("Çıkış",           self._quit_app),
            )
            self._tray = pystray.Icon("burkut", img, "BÜRKÜT", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception as e:
            print(f"[Widget] Tray hatası: {e}")

    # ── AI Chat ───────────────────────────────────────────────────────
    def _open_ai_chat(self):
        try:
            from widget.ai_chat import AIChatWindow
            AIChatWindow.get_or_create(self)
        except Exception as e:
            print(f"[Widget] AI chat açılamadı: {e}")

    def _hide(self):      self.withdraw()
    def _show(self, *_):  self.deiconify()

    def _toggle_topmost(self, *_):
        self._always_on_top = not self._always_on_top
        self.attributes("-topmost", self._always_on_top)
        try:
            from widget.widget_config import load_widget_config, save_widget_config
            cfg = load_widget_config()
            cfg["always_on_top"] = self._always_on_top
            save_widget_config(cfg)
        except Exception:
            pass

    def _quit_app(self, *_):
        try:  self._stop_ev.set()
        except Exception: pass
        try:  self._tray.stop()
        except Exception: pass
        self.destroy()

    def _pulse_ai_btn(self):
        if not self.winfo_exists():
            return
        colors = ["#1a2a1a", "#1e3020", "#223825", "#1e3020", "#1a2a1a"]
        borders = ["#2d4a2d", "#356035", "#3a6a3a", "#356035", "#2d4a2d"]
        try:
            idx = getattr(self, "_pulse_idx", 0)
            self._ai_btn.configure(fg_color=colors[idx], border_color=borders[idx])
            self._pulse_idx = (idx + 1) % len(colors)
        except Exception:
            pass
        self.after(700, self._pulse_ai_btn)

    def _check_ollama_status(self):
        if not self.winfo_exists():
            return

        def _probe():
            try:
                import requests
                r = requests.get("http://localhost:11434/api/tags", timeout=2)
                online = r.status_code == 200
            except Exception:
                online = False
            if self.winfo_exists():
                self.after(0, _apply, online)

        def _apply(online):
            if not self.winfo_exists():
                return
            try:
                color = "#3fb950" if online else "#f0a030"
                self._online_dot.configure(text_color=color)
            except Exception:
                pass
            self.after(30_000, self._check_ollama_status)

        threading.Thread(target=_probe, daemon=True).start()

    def run(self):
        self.mainloop()


def start_widget():
    widget = BurkutWidget()
    widget.run()


if __name__ == "__main__":
    start_widget()
