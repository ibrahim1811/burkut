import os
import threading

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model = None
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("BURKUT_EMBEDDINGS", "on").lower() not in ("off", "0", "false")


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(texts: list[str]):
    """list[str] → np.ndarray (n, 384) float32. Kapalıysa None."""
    if not enabled() or not texts:
        return None
    try:
        return _get_model().encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    except Exception:
        return None
