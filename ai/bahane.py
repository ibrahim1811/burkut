from typing import Optional

from ai.brain import _call_groq

MAX_COUNT = 10

_SYSTEM = (
    "Sen 'Bahane Üretici'sin. Kullanıcı bir durum verir (geç kalma, ödev yapmama, "
    "aramaya dönmeme vb.). Türkçe olarak tam {count} bahane üret. "
    "Bahaneler makulden absürde doğru sıralansın:\n"
    "- 🟢 Makul — gerçekten kullanılabilir, inandırıcı.\n"
    "- 🟡 Abartılı — biraz dramatik ama hâlâ yutulabilir.\n"
    "- 🔴 Efsane — tamamen saçma, absürt, komik.\n"
    "Her maddenin başına numarasını ve uygun emojiyi koy. Her biri 1-2 cümle, "
    "doğrudan karşı tarafa söylenecek şekilde yaz. Başlık, açıklama veya ek yorum "
    "ekleme; sadece numaralı {count} madde."
)


def generate_excuses(situation: str, count: int = 3, avoid: Optional[str] = None) -> Optional[str]:
    count = max(1, min(count, MAX_COUNT))
    user_msg = situation
    if avoid:
        user_msg += (
            "\n\nAşağıdaki bahaneleri zaten gördüm, beğenmedim. Bunlara benzemeyen, "
            f"tamamen farklı fikirler üret:\n{avoid}"
        )
    return _call_groq([
        {"role": "system", "content": _SYSTEM.format(count=count)},
        {"role": "user", "content": user_msg},
    ], timeout=60)
