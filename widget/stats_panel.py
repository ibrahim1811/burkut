"""
Sistem istatistikleri paneli.
"""
import psutil
import time

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGridLayout
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont


def _get_gpu_stats():
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem  = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        return {"usage": util.gpu, "vram_used": mem.used, "vram_total": mem.total, "temp": temp}
    except Exception:
        return None


class _StatsWorker(QThread):
    stats_ready = Signal(float, object, object, float, float)  # cpu, ram, gpu, dl, ul

    def __init__(self):
        super().__init__()
        self._running = True
        self._net_last = psutil.net_io_counters()
        self._net_last_time = time.time()

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                cpu  = psutil.cpu_percent(interval=1)
                ram  = psutil.virtual_memory()
                gpu  = _get_gpu_stats()
                net  = psutil.net_io_counters()
                t    = time.time()
                dt   = max(t - self._net_last_time, 0.001)
                dl   = (net.bytes_recv - self._net_last.bytes_recv) / dt
                ul   = (net.bytes_sent - self._net_last.bytes_sent) / dt
                self._net_last      = net
                self._net_last_time = t
                self.stats_ready.emit(cpu, ram, gpu, dl, ul)
            except Exception:
                # _running kontrol edilerek gereksiz bekleme önlenir
                if self._running:
                    time.sleep(2)


def _fmt_bytes(b: float) -> str:
    if b < 1024:       return f"{b:.0f} B/s"
    if b < 1048576:    return f"{b/1024:.1f} KB/s"
    return f"{b/1048576:.1f} MB/s"


class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._worker = _StatsWorker()
        self._worker.stats_ready.connect(self._apply)
        self._worker.start()

    def _make_row(self, label: str, color: str):
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #8b949e; font-size: 9px; font-weight: bold;")
        layout.addWidget(lbl)

        val_row = QWidget()
        val_layout = QHBoxLayout(val_row)
        val_layout.setContentsMargins(0, 0, 0, 0)

        val = QLabel("—")
        val.setStyleSheet("color: #f0f6fc; font-size: 15px; font-weight: bold;")
        val_layout.addWidget(val)

        sub = QLabel("")
        sub.setStyleSheet("color: #8b949e; font-size: 8px;")
        sub.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val_layout.addWidget(sub)

        layout.addWidget(val_row)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: #21262d; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {color}; border-radius: 1px; }}
        """)
        layout.addWidget(bar)

        return row, val, sub, bar

    def _build_ui(self):
        self.setStyleSheet("background: transparent;")
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(6)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(5)

        self._cpu_row, self._cpu_val, self._cpu_sub, self._cpu_bar = self._make_row("CPU",  "#58a6ff")
        self._ram_row, self._ram_val, self._ram_sub, self._ram_bar = self._make_row("RAM",  "#3fb950")
        self._gpu_row, self._gpu_val, self._gpu_sub, self._gpu_bar = self._make_row("GPU",  "#f78166")
        self._vrm_row, self._vrm_val, self._vrm_sub, self._vrm_bar = self._make_row("VRAM", "#d2a8ff")

        for w in (self._cpu_row, self._ram_row, self._gpu_row, self._vrm_row):
            w.setStyleSheet("background: #161b22; border-radius: 8px;")
            w.setContentsMargins(8, 6, 8, 6)

        grid.addWidget(self._cpu_row, 0, 0)
        grid.addWidget(self._ram_row, 0, 1)
        grid.addWidget(self._gpu_row, 1, 0)
        grid.addWidget(self._vrm_row, 1, 1)
        main.addWidget(grid_widget)

        # Network row
        net_row = QWidget()
        net_row.setStyleSheet("background: #161b22; border-radius: 6px;")
        net_layout = QHBoxLayout(net_row)
        net_layout.setContentsMargins(8, 4, 8, 4)

        net_icon = QLabel("🌐")
        net_icon.setStyleSheet("font-size: 10px;")
        net_layout.addWidget(net_icon)

        self._dl_lbl = QLabel("↓ —")
        self._dl_lbl.setStyleSheet("color: #79c0ff; font-size: 10px;")
        net_layout.addWidget(self._dl_lbl)

        self._ul_lbl = QLabel("↑ —")
        self._ul_lbl.setStyleSheet("color: #ff7b72; font-size: 10px;")
        net_layout.addWidget(self._ul_lbl)

        net_layout.addStretch()
        main.addWidget(net_row)

    def _apply(self, cpu: float, ram, gpu, dl: float, ul: float):
        self._cpu_val.setText(f"{cpu:.0f}%")
        self._cpu_bar.setValue(int(cpu))

        self._ram_val.setText(f"{ram.percent:.0f}%")
        self._ram_sub.setText(f"{ram.used/1073741824:.1f}/{ram.total/1073741824:.0f}G")
        self._ram_bar.setValue(int(ram.percent))

        if gpu:
            self._gpu_val.setText(f"{gpu['usage']:.0f}%")
            self._gpu_sub.setText(f"{gpu['temp']}°C")
            self._gpu_bar.setValue(int(gpu['usage']))
            vram_pct = gpu['vram_used'] / gpu['vram_total'] * 100
            self._vrm_val.setText(f"{gpu['vram_used']/1073741824:.1f}G")
            self._vrm_sub.setText(f"/{gpu['vram_total']/1073741824:.0f}G")
            self._vrm_bar.setValue(int(vram_pct))
        else:
            self._gpu_val.setText("—")
            self._vrm_val.setText("—")

        self._dl_lbl.setText(f"↓ {_fmt_bytes(dl)}")
        self._ul_lbl.setText(f"↑ {_fmt_bytes(ul)}")

    def stop(self):
        self._worker.stop()
        # quit() bu worker için no-op (run() Qt event loop kullanmıyor)
        # wait() ile thread'in doğal olarak bitmesini bekle (max 3 sn)
        self._worker.wait(3000)
