import customtkinter as ctk
import psutil
import threading
import time


def _get_gpu_stats():
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        return {
            "usage": util.gpu,
            "vram_used": mem.used,
            "vram_total": mem.total,
            "temp": temp,
        }
    except Exception:
        return None


class StatsPanel(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._net_last = psutil.net_io_counters()
        self._net_last_time = time.time()
        self._running = True

        self._build_ui()
        self._start_update_loop()

    def _build_ui(self):
        self.configure(fg_color="transparent")

        label_font = ctk.CTkFont(size=11, weight="bold")
        val_font   = ctk.CTkFont(size=11)

        self._cpu_label = ctk.CTkLabel(self, text="CPU", font=label_font, anchor="w")
        self._cpu_label.pack(fill="x", padx=8, pady=(6, 0))
        self._cpu_bar = ctk.CTkProgressBar(self, height=10, corner_radius=4)
        self._cpu_bar.pack(fill="x", padx=8, pady=(2, 0))
        self._cpu_val = ctk.CTkLabel(self, text="0%", font=val_font, anchor="e", text_color="gray")
        self._cpu_val.pack(fill="x", padx=8)

        self._ram_label = ctk.CTkLabel(self, text="RAM", font=label_font, anchor="w")
        self._ram_label.pack(fill="x", padx=8, pady=(4, 0))
        self._ram_bar = ctk.CTkProgressBar(self, height=10, corner_radius=4)
        self._ram_bar.pack(fill="x", padx=8, pady=(2, 0))
        self._ram_val = ctk.CTkLabel(self, text="0 GB / 0 GB", font=val_font, anchor="e", text_color="gray")
        self._ram_val.pack(fill="x", padx=8)

        self._gpu_label = ctk.CTkLabel(self, text="GPU", font=label_font, anchor="w")
        self._gpu_label.pack(fill="x", padx=8, pady=(4, 0))
        self._gpu_bar = ctk.CTkProgressBar(self, height=10, corner_radius=4)
        self._gpu_bar.pack(fill="x", padx=8, pady=(2, 0))
        self._gpu_val = ctk.CTkLabel(self, text="0% | VRAM: 0/0 GB", font=val_font, anchor="e", text_color="gray")
        self._gpu_val.pack(fill="x", padx=8)

        self._net_label = ctk.CTkLabel(self, text="AĞ", font=label_font, anchor="w")
        self._net_label.pack(fill="x", padx=8, pady=(4, 0))
        self._net_val = ctk.CTkLabel(self, text="↓ 0 KB/s  ↑ 0 KB/s", font=val_font, anchor="w", text_color="gray")
        self._net_val.pack(fill="x", padx=8, pady=(0, 4))

    def _update(self):
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory()

                net_now = psutil.net_io_counters()
                t_now = time.time()
                dt = max(t_now - self._net_last_time, 0.001)
                dl = (net_now.bytes_recv - self._net_last.bytes_recv) / dt
                ul = (net_now.bytes_sent - self._net_last.bytes_sent) / dt
                self._net_last = net_now
                self._net_last_time = t_now

                gpu = _get_gpu_stats()

                self.after(0, self._apply_stats, cpu, ram, gpu, dl, ul)
            except Exception:
                pass
            time.sleep(1)

    def _fmt_bytes(self, b):
        if b < 1024:
            return f"{b:.0f} B/s"
        elif b < 1024 ** 2:
            return f"{b/1024:.1f} KB/s"
        else:
            return f"{b/1024**2:.1f} MB/s"

    def _apply_stats(self, cpu, ram, gpu, dl, ul):
        try:
            self._cpu_bar.set(cpu / 100)
            self._cpu_val.configure(text=f"{cpu:.0f}%")

            ram_pct = ram.percent / 100
            ram_used_gb = ram.used / 1024**3
            ram_total_gb = ram.total / 1024**3
            self._ram_bar.set(ram_pct)
            self._ram_val.configure(text=f"{ram_used_gb:.1f} / {ram_total_gb:.1f} GB  {ram.percent:.0f}%")

            if gpu:
                gpu_pct = gpu["usage"] / 100
                vram_used_gb = gpu["vram_used"] / 1024**3
                vram_total_gb = gpu["vram_total"] / 1024**3
                self._gpu_bar.set(gpu_pct)
                self._gpu_val.configure(
                    text=f"{gpu['usage']}% | {vram_used_gb:.1f}/{vram_total_gb:.1f} GB | {gpu['temp']}°C"
                )
            else:
                self._gpu_bar.set(0)
                self._gpu_val.configure(text="GPU bilgisi alınamadı")

            self._net_val.configure(text=f"↓ {self._fmt_bytes(dl)}  ↑ {self._fmt_bytes(ul)}")
        except Exception:
            pass

    def _start_update_loop(self):
        t = threading.Thread(target=self._update, daemon=True)
        t.start()

    def stop(self):
        self._running = False
