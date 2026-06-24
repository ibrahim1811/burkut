import threading
import tkinter as tk


def show_overlay(text: str, duration: int = 8) -> None:
    """Ekran ortasında duration saniye görünen bildirim popup'ı."""
    def _run():
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)
        root.configure(bg="#1a1a2e")

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        frame = tk.Frame(root, bg="#1a1a2e", padx=30, pady=20)
        frame.pack()

        tk.Label(
            frame,
            text="🦅 BÜRKÜT",
            font=("Segoe UI", 11, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        ).pack()

        tk.Label(
            frame,
            text=text,
            font=("Segoe UI", 16),
            fg="#ffffff",
            bg="#1a1a2e",
            wraplength=500,
            justify="center",
        ).pack(pady=(8, 0))

        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        root.bind("<Button-1>", lambda e: root.destroy())
        root.after(duration * 1000, root.destroy)
        root.mainloop()

    threading.Thread(target=_run, daemon=True).start()
