import re
from typing import Optional


PATTERNS = [
    (r"bilgisayar[ıi] kapat|kapat|kapat[ıi]yor",               "shutdown",      []),
    (r"yeniden ba[sş]lat|restart|yeniden ba[sş]l[ıi]yor",      "restart",       []),
    (r"uyku( modu)?|uyusu?yor",                                 "sleep",         []),
    (r"haz[ıi]rda beklet|hazirda",                              "hibernate",     []),
    (r"ekran( g[oö]r[uü]nt[uü]s[uü])?( al)?|screenshot",       "screenshot",    []),
    (r"durum|sistem durumu|bilgiler|ne var",                     "status",        []),
    (r"ses[i]? a[cç]|sesi y[uü]kselt|ses y[uü]kselt|volume up","volume_up",     []),
    (r"ses[i]? k[ıi]s|sesi azalt|ses azalt|volume down",        "volume_down",   []),
    (r"sessiz|mute",                                            "mute",          []),
    (r"kilit|ekran[ıi] kilitle|kilitle",                        "lock",          []),
    (r"pano(da ne var)?|kopyala(nan)?",                         "clipboard",     []),
    (r"gpu|ekran kart[ıi]|grafik",                              "gpu",           []),
    (r"ses seviye[si]?\s*(\d+)|ses[i]? (\d+)[e]? getir",       "volume_set",    ["num"]),
    (r"parlakl[ıi]k\s*(\d+)|parlakl[ıi][ğg][ıi] (\d+)",       "brightness_set",["num"]),
    (r"pencereler|a[cç][ıi]k pencereler",                       "windows",       []),
    (r"widget g[oö]ster|widget a[cç]",                          "widget_show",   []),
    (r"widget gizle|widget kapat",                              "widget_hide",   []),
    (r"yardım|ne yapabilirsin|komutlar",                        "help",          []),
    (r"(.+?)\s+dosyas[ıi]n[ıi] a[cç]",                         "open_file",     ["match_1"]),
    (r"siteye git\s+(.+)|(.+?)\s+sitesini? a[cç]",             "open_url",      ["match_1_or_2"]),
    (r"(.+?)\s+klas[oö]r[uü]n[uü] a[cç]|(.+?)\s+klas[oö]r[uü] a[cç]", "open_folder", ["match_1_or_2"]),
    (r"(.+?)\s+a[cç]",                                         "launch",        ["match_1"]),
    (r"(.+?)\s+kapat",                                         "close_proc",    ["match_1"]),
]


def parse(text: str) -> tuple[str, list]:
    text_clean = text.strip().lower()

    for pattern, command, arg_spec in PATTERNS:
        m = re.search(pattern, text_clean, re.IGNORECASE)
        if not m:
            continue

        args = []
        for spec in arg_spec:
            if spec == "num":
                groups = [g for g in m.groups() if g is not None]
                if groups:
                    try:
                        args.append(int(groups[0]))
                    except ValueError:
                        args.append(None)
            elif spec.startswith("match_"):
                parts = spec.split("_")
                if "or" in parts:
                    for idx_str in parts[parts.index("or") + 1:]:
                        try:
                            idx = int(idx_str)
                            g = m.group(idx) if idx <= len(m.groups()) else None
                            if g:
                                args.append(g.strip())
                                break
                        except (IndexError, ValueError):
                            continue
                else:
                    try:
                        idx = int(parts[-1])
                        g = m.group(idx) if idx <= len(m.groups()) else None
                        args.append(g.strip() if g else "")
                    except (IndexError, ValueError):
                        args.append("")

        return command, args

    return "unknown", [text_clean]
