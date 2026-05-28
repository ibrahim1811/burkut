import glob
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

# ── Ortam değişkenleri ───────────────────────────────────────────────────────
_LOCAL   = os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local")
_ROAMING = os.environ.get("APPDATA",      r"C:\Users\Default\AppData\Roaming")
_PROG    = os.environ.get("PROGRAMFILES", r"C:\Program Files")
_PROG86  = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")

# ── Bilinen uygulama yolları (glob desteği: * → versiyonlu klasör) ───────────
# Her uygulama için sırayla denenir; ilk bulunan exe kullanılır.
KNOWN_APP_PATTERNS: dict[str, list[str]] = {
    # Tarayıcılar
    "opera":    [rf"{_LOCAL}\Programs\Opera GX\opera.exe"],
    "opera gx": [rf"{_LOCAL}\Programs\Opera GX\opera.exe"],
    "chrome":   [
        rf"{_LOCAL}\Google\Chrome\Application\chrome.exe",
        rf"{_PROG}\Google\Chrome\Application\chrome.exe",
        rf"{_PROG86}\Google\Chrome\Application\chrome.exe",
    ],
    "firefox":  [
        rf"{_PROG}\Mozilla Firefox\firefox.exe",
        rf"{_PROG86}\Mozilla Firefox\firefox.exe",
    ],
    "edge":     [
        rf"{_PROG}\Microsoft\Edge\Application\msedge.exe",
        rf"{_PROG86}\Microsoft\Edge\Application\msedge.exe",
    ],

    # İletişim
    "discord":  [rf"{_LOCAL}\Discord\app-*\Discord.exe"],   # * = versiyonlu klasör
    "telegram": [
        rf"{_ROAMING}\Telegram Desktop\Telegram.exe",
        rf"{_LOCAL}\Telegram Desktop\Telegram.exe",
    ],

    # Müzik / medya
    "spotify":  [
        rf"{_ROAMING}\Spotify\Spotify.exe",
        rf"{_LOCAL}\Spotify\Spotify.exe",
        rf"{_PROG}\Spotify\Spotify.exe",
    ],
    "vlc":      [
        rf"{_PROG}\VideoLAN\VLC\vlc.exe",
        rf"{_PROG86}\VideoLAN\VLC\vlc.exe",
    ],

    # Oyun
    "steam":    [
        rf"{_PROG86}\Steam\steam.exe",
        rf"{_PROG}\Steam\steam.exe",
        r"C:\Steam\steam.exe",
    ],

    # Geliştirme
    "vscode":   [rf"{_LOCAL}\Programs\Microsoft VS Code\Code.exe", rf"{_PROG}\Microsoft VS Code\Code.exe"],
    "code":     [rf"{_LOCAL}\Programs\Microsoft VS Code\Code.exe", rf"{_PROG}\Microsoft VS Code\Code.exe"],
    "vs code":  [rf"{_LOCAL}\Programs\Microsoft VS Code\Code.exe", rf"{_PROG}\Microsoft VS Code\Code.exe"],

    # Üretkenlik
    "word":       [rf"{_PROG}\Microsoft Office\root\Office16\WINWORD.EXE",
                   rf"{_PROG86}\Microsoft Office\root\Office16\WINWORD.EXE"],
    "excel":      [rf"{_PROG}\Microsoft Office\root\Office16\EXCEL.EXE",
                   rf"{_PROG86}\Microsoft Office\root\Office16\EXCEL.EXE"],
    "powerpoint": [rf"{_PROG}\Microsoft Office\root\Office16\POWERPNT.EXE",
                   rf"{_PROG86}\Microsoft Office\root\Office16\POWERPNT.EXE"],

    # Araçlar
    "obs":      [
        rf"{_PROG}\obs-studio\bin\64bit\obs64.exe",
        rf"{_PROG86}\obs-studio\bin\64bit\obs64.exe",
    ],
    "afterburner": [rf"{_PROG86}\MSI Afterburner\MSIAfterburner.exe"],
    "notepad++":   [
        rf"{_PROG}\Notepad++\notepad++.exe",
        rf"{_PROG86}\Notepad++\notepad++.exe",
    ],
    "winrar":   [
        rf"{_PROG}\WinRAR\WinRAR.exe",
        rf"{_PROG86}\WinRAR\WinRAR.exe",
    ],
    "7zip":     [
        rf"{_PROG}\7-Zip\7zFM.exe",
        rf"{_PROG86}\7-Zip\7zFM.exe",
    ],

    # Windows dahili — PATH'te olduğu için kısa ad yeterli
    "notepad":     ["notepad.exe"],
    "not defteri": ["notepad.exe"],
    "calc":        ["calc.exe"],
    "calculator":  ["calc.exe"],
    "hesap makinesi": ["calc.exe"],
    "paint":       ["mspaint.exe"],
    "explorer":    ["explorer.exe"],
    "dosya gezgini": ["explorer.exe"],
    "taskmgr":     ["taskmgr.exe"],
    "görev yöneticisi": ["taskmgr.exe"],
    "cmd":         ["cmd.exe"],
    "powershell":  ["powershell.exe"],
    "snipping":    ["snippingtool.exe"],
    "ekran alıntısı": ["snippingtool.exe"],
}

# Türkçe ek / takma ad → normalize
_TR_ALIASES: dict[str, str] = {
    "google chrome":     "chrome",
    "mozilla firefox":   "firefox",
    "microsoft edge":    "edge",
    "vs code":           "vscode",
    "visual studio code": "vscode",
    "opera gx browser":  "opera gx",
    "discord uygulaması": "discord",
    "spotify müzik":     "spotify",
    "steam platform":    "steam",
    "not defteri":       "notepad",
    "hesap makinesi":    "calc",
    "dosya gezgini":     "explorer",
    "görev yöneticisi":  "taskmgr",
    "ekran alıntısı":    "snipping",
}

# ── Site URL eşleştirmesi (sadece open_url / ses komutları için) ─────────────
WEBSITE_ALIASES: dict[str, str] = {
    "youtube": "https://youtube.com",
    "google":  "https://google.com",
    "gmail":   "https://mail.google.com",
    "mail":    "https://mail.google.com",
    "twitter": "https://twitter.com",
    "x":       "https://x.com",
    "instagram": "https://instagram.com",
    "netflix":  "https://netflix.com",
    "twitch":   "https://twitch.tv",
    "github":   "https://github.com",
    "reddit":   "https://reddit.com",
    "chatgpt":  "https://chat.openai.com",
    "chat gpt": "https://chat.openai.com",
    "claude":   "https://claude.ai",
    "wikipedia": "https://tr.wikipedia.org",
    "ekşi":     "https://eksisozluk.com",
    "eksi":     "https://eksisozluk.com",
    "trendyol": "https://trendyol.com",
    "amazon":   "https://amazon.com.tr",
    "drive":    "https://drive.google.com",
    "steam mağaza": "https://store.steampowered.com",
}

# Tarayıcı adı → exe (open_url_in için) ─────────────────────────────────────
BROWSER_EXES: dict[str, str] = {
    "opera":            rf"{_LOCAL}\Programs\Opera GX\opera.exe",
    "opera gx":         rf"{_LOCAL}\Programs\Opera GX\opera.exe",
    "chrome":           rf"{_LOCAL}\Google\Chrome\Application\chrome.exe",
    "google chrome":    rf"{_LOCAL}\Google\Chrome\Application\chrome.exe",
    "firefox":          rf"{_PROG}\Mozilla Firefox\firefox.exe",
    "mozilla":          rf"{_PROG}\Mozilla Firefox\firefox.exe",
    "edge":             rf"{_PROG}\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge":   rf"{_PROG}\Microsoft\Edge\Application\msedge.exe",
}


# ── Exe bulma ─────────────────────────────────────────────────────────────────

def find_app_exe(name: str) -> Optional[str]:
    """
    Uygulama adına göre exe yolunu bul.
    Sırasıyla: bilinen yollar → glob → where komutu
    """
    key = name.lower().strip()
    key = _TR_ALIASES.get(key, key)  # Türkçe alias normalize

    patterns = KNOWN_APP_PATTERNS.get(key, [])

    for pattern in patterns:
        if "*" in pattern:
            # Versiyonlu klasör (Discord app-1.0.xxx)
            matches = sorted(glob.glob(pattern))
            if matches:
                return matches[-1]  # en yüksek sürüm
        else:
            p = Path(pattern)
            if p.exists():
                return str(p)

    # Bilinen listede yoksa: where komutu ile PATH'te ara
    try:
        result = subprocess.run(
            ["where", name],
            capture_output=True, text=True, timeout=4,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.lower().endswith(".exe") and os.path.exists(line):
                    return line
    except Exception:
        pass

    return None


# ── Uygulama açma ─────────────────────────────────────────────────────────────

def open_app(name_or_path: str) -> tuple[bool, str]:
    """Masaüstü uygulamasını açar. Tarayıcıya yönlendirmez."""
    # Türkçe iyelik eki temizle: "discord'u" → "discord"
    name_lower = name_or_path.lower().strip()
    for apos in ("'", "’", "ʼ"):
        if apos in name_lower:
            name_lower = name_lower.split(apos)[0].strip()
            break

    # 1. Tam yol verilmişse direkt aç
    if os.path.exists(name_or_path):
        try:
            subprocess.Popen(
                [name_or_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"✅ Açıldı: `{Path(name_or_path).name}`"
        except Exception as e:
            return False, f"❌ Açılamadı: {e}"

    # 2. Exe yolunu bul (bilinen + glob + where)
    exe = find_app_exe(name_lower)
    if exe:
        try:
            subprocess.Popen(
                [exe],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"✅ Açıldı: `{Path(exe).name}`"
        except Exception as e:
            return False, f"❌ {Path(exe).name} açılamadı: {e}"

    # 3. Son çare: shell=True ile adı çalıştır (PATH'teki araçlar)
    try:
        subprocess.Popen(
            name_lower,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True, f"✅ Çalıştırıldı: `{name_lower}`"
    except Exception as e:
        return False, f"❌ Uygulama bulunamadı: `{name_lower}` — {e}"


# ── Belirli tarayıcıda URL aç ─────────────────────────────────────────────────

def open_url_in_browser(browser: str, url: str) -> tuple[bool, str]:
    """URL'yi istenen masaüstü tarayıcısında açar."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    key = browser.lower().strip()

    # Önce BROWSER_EXES'te ara
    exe = BROWSER_EXES.get(key)

    # Yoksa find_app_exe ile bul
    if not exe or not os.path.exists(exe):
        exe = find_app_exe(key)

    if not exe:
        # Son çare: shell=True
        try:
            subprocess.Popen(
                f'"{browser}" "{url}"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True, f"✅ {browser.title()} ile açıldı: `{url}`"
        except Exception as e:
            return False, f"❌ {browser} bulunamadı: {e}"

    try:
        subprocess.Popen(
            [exe, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, f"✅ {browser.title()} ile açıldı: `{url}`"
    except Exception as e:
        return False, f"❌ {browser} açılamadı: {e}"


# ── Varsayılan tarayıcıda URL aç ──────────────────────────────────────────────

def open_url(url: str) -> tuple[bool, str]:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return True, f"✅ Açıldı: `{url}`"
    except Exception as e:
        return False, f"❌ URL açılamadı: {e}"


# ── Klasör / dosya / Steam ────────────────────────────────────────────────────

def open_folder(path: str) -> tuple[bool, str]:
    p = Path(path).expanduser()
    if not p.exists():
        return False, f"❌ Klasör bulunamadı: `{path}`"
    try:
        os.startfile(str(p))
        return True, f"✅ Klasör açıldı: `{p.name}`"
    except Exception as e:
        return False, f"❌ Klasör açılamadı: {e}"


def open_file(path: str) -> tuple[bool, str]:
    p = Path(path).expanduser()
    if not p.exists():
        return False, f"❌ Dosya bulunamadı: `{path}`"
    try:
        os.startfile(str(p))
        return True, f"✅ Dosya açıldı: `{p.name}`"
    except Exception as e:
        return False, f"❌ Dosya açılamadı: {e}"


def open_steam_game(game_id: str) -> tuple[bool, str]:
    url = f"steam://rungameid/{game_id}"
    try:
        webbrowser.open(url)
        return True, f"✅ Steam oyunu başlatılıyor (ID: {game_id})"
    except Exception as e:
        return False, f"❌ Steam oyunu başlatılamadı: {e}"


def find_and_open(query: str, search_paths: list[str] = None) -> tuple[bool, str]:
    if search_paths is None:
        search_paths = [
            str(Path.home() / "Desktop"),
            str(Path.home() / "Documents"),
            str(Path.home() / "Downloads"),
        ]
    query_lower = query.lower()
    for base in search_paths:
        base_path = Path(base)
        if not base_path.exists():
            continue
        for f in base_path.rglob("*"):
            if query_lower in f.name.lower() and f.is_file():
                return open_file(str(f))
    return False, f"❌ Dosya bulunamadı: `{query}`"
