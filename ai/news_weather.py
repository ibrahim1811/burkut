"""
Hava durumu (wttr.in) ve haber (Google News RSS) modülü.
API anahtarı gerektirmez.
"""

import requests
import xml.etree.ElementTree as ET

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 10

NEWS_FEEDS = {
    "genel":      "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr",
    "teknoloji":  "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtcHlHZ0pVVWlnQVAB?hl=tr&gl=TR&ceid=TR:tr",
    "spor":       "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGQ2TVhZU0FtcHlHZ0pVVWlnQVAB?hl=tr&gl=TR&ceid=TR:tr",
    "ekonomi":    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxTlhZU0FtcHlHZ0pVVWlnQVAB?hl=tr&gl=TR&ceid=TR:tr",
    "dunya":      "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlhZU0FtcHlHZ0pVVWlnQVAB?hl=tr&gl=TR&ceid=TR:tr",
    "bilim":      "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RZU0FtcHlHZ0pVVWlnQVAB?hl=tr&gl=TR&ceid=TR:tr",
}


def get_weather(city: str = "Istanbul") -> str:
    """wttr.in üzerinden hava durumu bilgisi."""
    try:
        resp = requests.get(
            f"https://wttr.in/{city}?format=j1",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        cur = data["current_condition"][0]
        temp      = cur["temp_C"]
        feels     = cur["FeelsLikeC"]
        desc      = cur["weatherDesc"][0]["value"]
        humidity  = cur["humidity"]
        wind      = cur["windspeedKmph"]
        vis       = cur.get("visibility", "?")
        uv        = cur.get("uvIndex", "?")

        # Bugün min/max
        today = data["weather"][0]
        tmin, tmax = today["mintempC"], today["maxtempC"]
        sunrise = today.get("astronomy", [{}])[0].get("sunrise", "?")
        sunset  = today.get("astronomy", [{}])[0].get("sunset", "?")

        # Yarın
        tomorrow_str = ""
        if len(data["weather"]) > 1:
            tm = data["weather"][1]
            tm_desc = tm["hourly"][4]["weatherDesc"][0]["value"]
            tomorrow_str = f"\n🔮 *Yarın:* {tm_desc}, {tm['mintempC']}–{tm['maxtempC']}°C"

        lines = [
            f"🌤️ *{city} Hava Durumu*",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"🌡️ Sıcaklık: `{temp}°C`  (Hissedilen `{feels}°C`)",
            f"☁️ Durum: {desc}",
            f"🌡️ Gün: `{tmin}–{tmax}°C`",
            f"💧 Nem: `%{humidity}`",
            f"💨 Rüzgar: `{wind} km/s`",
            f"👁️ Görüş: `{vis} km`",
            f"☀️ UV: `{uv}`",
            f"🌅 Gün doğumu/batımı: `{sunrise}` / `{sunset}`",
            tomorrow_str,
        ]
        return "\n".join(l for l in lines if l)

    except Exception as e:
        return f"❌ Hava durumu alınamadı: {e}"


def get_news(category: str = "genel", count: int = 8) -> str:
    """Google News RSS'ten son haberler."""
    category = category.lower().strip()
    feed_url = NEWS_FEEDS.get(category, NEWS_FEEDS["genel"])
    cat_label = category.capitalize()

    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return "❌ RSS parse hatası."

        items = channel.findall("item")[:count]
        lines = [f"📰 *Son Haberler — {cat_label}*", "━━━━━━━━━━━━━━━━━━━━━━"]

        for i, item in enumerate(items, 1):
            title = item.findtext("title", "").split(" - ")[0].strip()
            pub = item.findtext("pubDate", "")
            # pubDate örn: "Sat, 24 May 2026 10:00:00 GMT"
            pub_short = pub[5:16] if pub else ""
            lines.append(f"{i}. {title}")
            if pub_short:
                lines.append(f"   _{pub_short}_")

        lines.append(f"\n_Kategoriler: {', '.join(NEWS_FEEDS.keys())}_")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ Haberler alınamadı: {e}"


def get_available_categories() -> str:
    cats = ", ".join(f"`{k}`" for k in NEWS_FEEDS.keys())
    return f"Mevcut kategoriler: {cats}"
