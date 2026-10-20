from typing import Optional

from ai.brain import _call_groq

_SYSTEM = (
    "Sen 'Bahane Üretici'sin. Kullanıcı bir durum verir (geç kalma, ödev yapmama, "
    "aramaya dönmeme vb.). Türkçe olarak tam 3 bahane üret:\n"
    "1. 🟢 Makul — gerçekten kullanılabilir, inandırıcı.\n"
    "2. 🟡 Abartılı — biraz dramatik ama hâlâ yutulabilir.\n"
    "3. 🔴 Efsane — tamamen saçma, absürt, komik.\n"
    "Her biri 1-2 cümle, doğrudan karşı tarafa söylenecek şekilde yaz. "
    "Başlık, açıklama veya ek yorum ekleme; sadece numaralı 3 madde."
)


def generate_excuses(situation: str) -> Optional[str]:
    return _call_groq([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": situation},
    ], timeout=60)
