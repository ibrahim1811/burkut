from typing import Optional

from ai.brain import _call_groq

_SYSTEM = (
    "Sen 'Cevap Yazıcı'sın. Kullanıcı birinden gelen bir mesajı yapıştırır. "
    "O mesaja kullanıcı adına gönderilecek Türkçe 3 farklı cevap yaz:\n"
    "1. 🧊 Soğuk — kısa, mesafeli, net.\n"
    "2. 😄 Esprili — samimi, komik, gülümseten.\n"
    "3. 🗡️ Laf sokan — kibar görünen ama iğneleyici, pasif-agresif.\n"
    "Cevaplar doğal bir mesajlaşma dilinde, 1-3 cümle olsun. Hakaret ve küfür yok. "
    "Başlık veya açıklama ekleme; sadece numaralı ve emojili 3 madde."
)


def generate_replies(message: str, avoid: Optional[str] = None) -> Optional[str]:
    user_msg = f"Gelen mesaj:\n{message}"
    if avoid:
        user_msg += (
            "\n\nAşağıdaki cevapları beğenmedim. Bunlara benzemeyen, "
            f"tamamen farklı cevaplar yaz:\n{avoid}"
        )
    return _call_groq([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_msg},
    ], timeout=60)
