"""Ses asistanı ile widget arasında paylaşılan durum."""
_indicator = None


def set_indicator(ind) -> None:
    global _indicator
    _indicator = ind


def get_indicator():
    return _indicator


def find_real_mic() -> int | None:
    """Steam/sanal mikrofonu atlayıp gerçek fiziksel mikrofonu döner.
    Bulamazsa None (sounddevice varsayılanı kullanılır).
    """
    try:
        import sounddevice as sd

        # Tercih sırası: Realtek > Intel Smart Sound > diğerleri
        PREFER   = ["realtek", "intel® smart sound", "dijital mikrof", "dizisi"]
        SKIP     = ["steam", "nvidia broadcast", "microsoft ses", "birincil ses",
                    "rtx-audio", "karışımı", "hoparlör", "stereo mix",
                    "wave", "output", "input ("]

        devices  = sd.query_devices()
        best     = None
        best_pri = 99

        for i, d in enumerate(devices):
            if d["max_input_channels"] < 1:
                continue
            name_low = d["name"].lower()
            if any(s in name_low for s in SKIP):
                continue
            pri = next(
                (j for j, p in enumerate(PREFER) if p in name_low),
                len(PREFER),
            )
            if pri < best_pri:
                best_pri = pri
                best = i

        if best is not None:
            print(f"[Mic] Seçilen mikrofon [{best}]: {devices[best]['name']}")
        return best
    except Exception:
        return None


_real_mic_idx: int | None = -1   # -1 = henüz aranmadı


def get_mic_device() -> int | None:
    """İlk çağrıda mikrofonu arar, sonrasında önbelleği döner."""
    global _real_mic_idx
    if _real_mic_idx == -1:
        _real_mic_idx = find_real_mic()
    return _real_mic_idx
