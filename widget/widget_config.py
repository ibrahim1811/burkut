import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

DEFAULT_WIDGET = {
    "position_x": None,
    "position_y": 100,
    "width": 280,
    "opacity": 0.92,
    "always_on_top": False,
    "theme": "dark",
    "launchers": [
        {"label": "Chrome",    "icon": "🌐", "type": "app",    "path": "chrome"},
        {"label": "Steam",     "icon": "🎮", "type": "app",    "path": "steam"},
        {"label": "Discord",   "icon": "💬", "type": "app",    "path": "discord"},
        {"label": "YouTube",   "icon": "▶",  "type": "url",    "path": "https://youtube.com"},
        {"label": "Belgelerim","icon": "📁", "type": "folder", "path": "~/Documents"},
    ],
}


def load_widget_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        widget_cfg = cfg.get("widget", {})
        merged = {**DEFAULT_WIDGET, **widget_cfg}
        merged["launchers"] = widget_cfg.get("launchers", DEFAULT_WIDGET["launchers"])
        return merged
    except Exception:
        return DEFAULT_WIDGET.copy()


def save_widget_config(widget_cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["widget"] = widget_cfg
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Widget config kayıt hatası: {e}")


def get_launchers() -> list:
    return load_widget_config().get("launchers", [])


def save_launchers(launchers: list) -> None:
    cfg = load_widget_config()
    cfg["launchers"] = launchers
    save_widget_config(cfg)


def add_launcher(label: str, icon: str, type_: str, path: str) -> None:
    launchers = get_launchers()
    launchers.append({"label": label, "icon": icon, "type": type_, "path": path})
    save_launchers(launchers)


def remove_launcher(index: int) -> None:
    launchers = get_launchers()
    if 0 <= index < len(launchers):
        launchers.pop(index)
        save_launchers(launchers)


def save_position(x: int, y: int) -> None:
    cfg = load_widget_config()
    cfg["position_x"] = x
    cfg["position_y"] = y
    save_widget_config(cfg)
