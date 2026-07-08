# Bürküt OS — Memory Engine Tasarımı

> Faz 2 (MVP çekirdeği). İlgili dokümanlar: `03-database.md` (şema), `04-api.md` (memory endpoint'leri).

Memory Engine, Bürküt'ün kullanıcıyı zamanla tanımasını sağlayan katmandır: projeler, dersler, hedefler, alışkanlıklar, sık kullanılan programlar ve öğrenilen web kaynakları burada saklanır, aranır ve her AI çağrısına bağlam olarak enjekte edilir.

## 1. Bellek Modeli

| Katman | Kapsam | Saklama | Yaşam süresi |
|---|---|---|---|
| **Kısa süreli** | Aktif konuşma oturumu (son N mesaj) | `conversations` + `messages` tabloları | Oturum boyunca; özetlenince uzun süreliye damıtılır |
| **Uzun süreli** | Kalıcı anılar: fact / preference / event / note / project | `memories` tablosu + FTS5 + embedding | Kalıcı (opsiyonel `expires_at`) |

Kısa süreli bellek mevcut `ai/memory.py` oturum mantığının SQLite'a taşınmış hâlidir. Uzun süreli bellek yeni `memory/` paketiyle gelir.

### Anı tipleri (`memories.kind`)
- `fact` — "Kayra İzmir'de yaşıyor", "Python 3.11 kullanıyor"
- `preference` — "kısa cevap sever", "koyu tema kullanır"
- `event` — "8 Temmuz'da fizik sınavı vardı"
- `note` — kullanıcının açıkça "bunu hatırla" dedikleri
- `project` — aktif projeler ve durumları (PcBot, ders çalışması...)

## 2. Modül Yapısı (`memory/` paketi)

```
memory/
├── store.py            # SQLite CRUD + FTS5 senkronizasyonu
├── embedder.py         # sentence-transformers lazy-load, batch embed
├── search.py           # hybrid arama (BM25 + kosinüs) + RRF birleştirme
├── ranker.py           # skor = benzerlik × recency_decay × importance
├── context_builder.py  # token bütçeli RAG bağlam paketi
└── migrate_json.py     # memory.json → SQLite tek seferlik göç
```

## 3. Embedding Stratejisi

**Model:** `sentence-transformers` + **`paraphrase-multilingual-MiniLM-L12-v2`**
- 384 boyutlu vektör, 50+ dil (Türkçe dahil), CPU'da yeterince hızlı
- Tamamen ücretsiz ve offline — bütçe kararıyla (ücretsiz ağırlıklı) uyumlu
- İlk kurulum maliyeti: torch dahil ~1.5 GB disk, çalışırken ~470 MB RAM

**Neden Groq embedding değil?** Groq'un embedding API'si yok (yalnızca chat/completion + Whisper). Ücretli embedding API'leri (OpenAI, Voyage) bütçe kararına aykırı. Tek gerçekçi bedava yol yerel modeldir. Ollama kuruluysa `bge-m3` gelecekte opsiyonel alternatif olarak eklenebilir.

**Çalışma kuralları:**
- **Lazy-load:** model ilk embed çağrısında yüklenir; bot/widget açılışını yavaşlatmaz.
- **Kill-switch:** `BURKUT_EMBEDDINGS=off` env değişkeni → model hiç yüklenmez, arama **FTS-only moda** düşer. Düşük RAM'li makinede sistem çalışmaya devam eder.
- **Batch embed:** yeni anılar kuyruklanır, ayrı düşük öncelikli thread'de toplu embed edilir; ses/widget performansı etkilenmez.
- Vektörler `memories.embedding` BLOB kolonunda `float32[384]` (little-endian) olarak saklanır.
- **Render'a asla deploy edilmez** — sentence-transformers yalnızca yerel `requirements` tarafında (`sys_platform == "win32"`).

## 4. Hybrid Search

Türkçe morfolojisi (ekler, çekimler) yüzünden salt vektör aramaya güvenilmez; salt anahtar kelime araması da eş anlamlıları kaçırır. İkisi birleştirilir:

1. **FTS5 / BM25** — `memories_fts` sanal tablosu, tokenizer: `unicode61 remove_diacritics 2` (ı/i, ş/s, ğ/g eşleşmesi için).
2. **Vektör benzerliği** — sorgu embed edilir, tüm anı vektörleriyle **numpy kosinüs** benzerliği hesaplanır. Veri < 100k satırken tam tarama yeterlidir (384 float × 100k ≈ 150 MB, milisaniyeler); `sqlite-vec` uzantısı ancak bu eşik aşılınca eklenir.
3. **Birleştirme** — Reciprocal Rank Fusion (RRF): `skor(d) = Σ 1/(k + rank_i(d))`, k=60. İki listede de geçen sonuçlar öne çıkar.

## 5. Ranking

Ham arama skoru tek başına yetmez; anının tazeliği ve önemi de sayılır:

```
final_score = similarity × recency_decay × importance

recency_decay = 0.5 ^ (gün_farkı / half_life)     # half_life varsayılan 90 gün
importance    = memories.importance (0.0–1.0, varsayılan 0.5)
```

- `last_accessed` her erişimde güncellenir, `access_count` artar → sık kullanılan anılar dolaylı olarak taze kalır.
- `preference` ve `project` tipleri için half_life daha uzun (365 gün) — alışkanlıklar hızlı eskimez.

## 6. Context Builder (RAG)

`context_builder.build(query, token_budget=1500)`:

1. Sorguyu hybrid search'ten geçirir, ranker ile sıralar.
2. Token bütçesine sığana kadar en yüksek skorlu anıları seçer (yaklaşık sayım: `len(text) / 3` — Türkçe için kaba ama yeterli).
3. Çıktı biçimi — sistem prompt'una eklenen blok:

```
## Kullanıcı hakkında bildiklerin
- [project] PcBot'u Bürküt OS'a evriltiyor (skor 0.91)
- [event] 8 Temmuz'da fizik sınavı vardı (skor 0.74)
...
```

**Entegrasyon:** `ai/brain.py` → `_build_system_prompt` içine tek çağrı eklenir; her Groq isteği öncesi ilgili anılar otomatik enjekte edilir. `<EYLEM>` protokolü ve mevcut akış değişmez.

## 7. Otomatik Anı Çıkarımı

Her sohbet turundan sonra (ayrı bir Groq çağrısı **açılmaz**, maliyet için):
- Ana yanıt çağrısının sistem prompt'una küçük bir ek talimat konur: yanıtın sonunda opsiyonel `<ANI>{"kind":"fact","content":"...","importance":0.7}</ANI>` bloğu üretmesi istenir (mevcut `<EYLEM>` deseniyle aynı ayrıştırma altyapısı).
- Blok varsa ayrıştırılıp `memories`'e yazılır; embed kuyruğuna eklenir.
- Tekrar koruması: yeni anı, en benzer mevcut anıyla kosinüs > 0.92 ise yazılmaz, mevcut anının `importance` ve `last_accessed` değeri güncellenir.
- Kullanıcının açık "bunu hatırla / unut" komutları her zaman önceliklidir (`note` tipi, importance 1.0 / soft-delete).

## 8. memory.json → SQLite Göçü

**İlke: geri dönüşlü, kademeli, imza-koruyan.**

1. **`migrate_json.py`** (tek seferlik, bot kapalıyken çalıştırılır): `conversations`, `projects`, `files`, `reminders` ve öğrenilen web kaynakları SQLite'a eşlenir. `memory.json` **silinmez**, `memory.json.bak` olarak korunur → rollback her zaman mümkün.
2. **Adapter dönemi:** `ai/memory.py`'ın mevcut fonksiyon imzaları (`add_message`, `get_session_messages`, ...) aynen korunur; içleri SQLite'a yönlendirilir. `brain.py`, `bot/handlers.py` ve widget **hiç değişmeden** çalışmaya devam eder.
3. **Dual-write dönemi:** Telegram bot tarafı tam doğrulanana kadar yazımlar hem SQLite'a hem memory.json'a gider; okuma SQLite'tan yapılır. Tutarsızlık riski bu pencereyle sınırlıdır.
4. **Kapanış:** doğrulama sonrası memory.json read-only'ye alınır, dual-write kapatılır.

## 9. Doğrulama

- `python -m memory.search "sınav"` tarzı CLI ile Türkçe sorguda anlamlı sonuç (diakritik varyantlarıyla: "sinav" da eşleşmeli).
- Sohbette geçmiş bir anının bağlama girdiği gözlemlenir (ör. önce "yarın sınavım var" de, sonraki oturumda "yarın ne yapıyordum?" sor).
- `BURKUT_EMBEDDINGS=off` ile FTS-only modun çalıştığı doğrulanır.
- Göç sonrası Telegram komutları regresyon testi (smoke-test).
