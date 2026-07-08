from memory.search import search

CHAR_BUDGET = 2400  # ~600 token


def build(query: str, top_k: int = 5) -> str:
    """Sorguyla ilgili anıları sistem prompt'una eklenecek blok olarak döndür."""
    try:
        results = search(query, top_k=top_k)
    except Exception:
        return ""
    if not results:
        return ""
    lines, used = [], 0
    for r in results:
        line = f"- {r['content'].strip()}"
        if used + len(line) > CHAR_BUDGET:
            break
        lines.append(line)
        used += len(line)
    if not lines:
        return ""
    return "Kayra hakkinda hatirladiklarin (gerekirse kullan):\n" + "\n".join(lines)
