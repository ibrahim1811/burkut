"""
Web sayfası okuyucu — URL'lerden içerik, kod blokları ve meta bilgisi çıkarır.
"""

import re
import requests
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15
MAX_CHARS = 6000


def fetch_url(url: str, max_chars: int = MAX_CHARS) -> dict:
    """URL'yi getir, yapılandırılmış veri döndür."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")

        if "text/html" in ct:
            return _parse_html(url, resp.text, max_chars)
        elif "application/json" in ct:
            return {"type": "json", "url": url, "content": resp.text[:max_chars], "title": url}
        elif "text/" in ct:
            return {"type": "text", "url": url, "content": resp.text[:max_chars], "title": url}
        else:
            return {"type": "binary", "url": url, "content": f"İkili dosya ({ct})", "title": url}
    except requests.exceptions.ConnectionError:
        return {"type": "error", "url": url, "error": "Bağlantı kurulamadı"}
    except requests.exceptions.Timeout:
        return {"type": "error", "url": url, "error": "Zaman aşımı"}
    except Exception as e:
        return {"type": "error", "url": url, "error": str(e)}


def _parse_html(url: str, html: str, max_chars: int) -> dict:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # BeautifulSoup yoksa ham text
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()[:max_chars]
        return {"type": "html_raw", "url": url, "content": text, "title": url}

    soup = BeautifulSoup(html, "html.parser")

    # Gereksiz elementleri kaldır
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "iframe", "svg", "form"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else urlparse(url).netloc

    # Kod blokları
    code_blocks = []
    for code in soup.find_all(["pre", "code"]):
        cb = code.get_text(strip=True)
        if len(cb) > 30:
            lang = code.get("class", [""])[0].replace("language-", "") if code.get("class") else ""
            code_blocks.append({"lang": lang, "code": cb[:2000]})

    # Bağlantılar
    links = []
    for a in soup.find_all("a", href=True)[:15]:
        href = a["href"]
        text = a.get_text(strip=True)
        if href.startswith("http") and text and len(text) < 100:
            links.append({"text": text, "href": href})

    # Ana içerik (önce <main> / <article>, yoksa <body>)
    main = soup.find("main") or soup.find("article") or soup.find("div", id="content") or soup.find("body")
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()[:max_chars]

    return {
        "type": "html",
        "url": url,
        "title": title,
        "content": text,
        "code_blocks": code_blocks[:8],
        "links": links[:10],
    }


def extract_github_raw(url: str) -> dict:
    """GitHub blob URL'sini raw içeriğe çevirir."""
    if "github.com" in url and "/blob/" in url:
        raw_url = (
            url.replace("github.com", "raw.githubusercontent.com")
               .replace("/blob/", "/")
        )
        return fetch_url(raw_url)
    return fetch_url(url)


def format_for_ai(result: dict, max_chars: int = 4000) -> str:
    """AI'ya gönderilecek URL içeriğini formatla."""
    if result.get("type") == "error":
        return f"[URL HATASI: {result['error']}]"

    lines = [f"[URL: {result['url']}]", f"Başlık: {result.get('title', '')}"]

    content = result.get("content", "")[:max_chars]
    if content:
        lines.append(f"\nİçerik:\n{content}")

    code_blocks = result.get("code_blocks", [])
    if code_blocks:
        lines.append(f"\nKod Blokları ({len(code_blocks)} adet):")
        for cb in code_blocks[:3]:
            lang = cb.get("lang", "")
            lines.append(f"```{lang}\n{cb['code'][:500]}\n```")

    return "\n".join(lines)


def extract_key_facts(result: dict, max_facts: int = 12) -> list:
    """HTML parse sonucundan anahtar bilgileri liste olarak çıkar."""
    facts = []
    title = result.get("title", "")
    if title:
        facts.append(f"Başlık: {title}")

    content = result.get("content", "")
    if content:
        sentences = re.split(r"(?<=[.!?])\s+", content)
        for sent in sentences:
            sent = sent.strip()
            if 40 < len(sent) < 400:
                facts.append(sent)
                if len(facts) >= max_facts:
                    break

    code_blocks = result.get("code_blocks", [])
    if code_blocks:
        facts.append(f"{len(code_blocks)} kod bloğu içeriyor")

    return facts[:max_facts]


def format_result_summary(result: dict) -> str:
    """Önceden getirilmiş bir fetch sonucunu kullanıcı dostu metne çevir."""
    url = result.get("url", "")
    title = result.get("title", url)
    content = result.get("content", "")
    code_blocks = result.get("code_blocks", [])
    links = result.get("links", [])

    lines = [f"🌐 **{title}**", f"🔗 {url}", ""]

    if content:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) > 40]
        for p in paragraphs[:7]:
            lines.append(p[:700])
            lines.append("")

    if code_blocks:
        lines.append(f"📝 **{len(code_blocks)} Kod Bloğu:**")
        for cb in code_blocks[:3]:
            lang = cb.get("lang", "")
            lines.append(f"```{lang}")
            lines.append(cb["code"][:800])
            lines.append("```")
            lines.append("")

    if links:
        lines.append("🔗 **Bağlantılar:**")
        for lnk in links[:5]:
            lines.append(f"• {lnk['text']}: {lnk['href']}")

    return "\n".join(lines)


def python_summarize_url(url: str) -> str:
    """URL'yi Python ile oku ve Türkçe özet üret. Ollama gerektirmez."""
    result = fetch_url(url)
    if result.get("type") == "error":
        return f"❌ URL okunamadı: {result['error']}\n🔗 {url}"
    return format_result_summary(result)


def detect_urls(text: str) -> list:
    """Metindeki URL'leri tespit et."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(pattern, text)
