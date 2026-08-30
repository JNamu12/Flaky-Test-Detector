import hashlib
import numpy as np

import os

_model = None

def get_model():
    global _model
    if _model is None:
        if os.getenv("USE_LOCAL_EMBEDDINGS", "false").lower() == "true":
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer('BAAI/bge-small-en-v1.5')
            except Exception as e:
                print(f"SentenceTransformer fallback enabled: {e}")
                _model = False
        else:
            _model = False
    return _model

def embed_text(text: str):
    """Return a dense vector embedding for the given text (384-dim)."""
    model = get_model()
    if model:
        try:
            return model.encode([text], normalize_embeddings=True)[0].tolist()
        except Exception as e:
            print(f"Embedding encoding fallback: {e}")

    # Lightweight deterministic 384-dim vector fallback to prevent OOM on 512MB RAM
    vec = []
    for i in range(384):
        h = hashlib.sha256(f"{text}_{i}".encode('utf-8')).hexdigest()
        val = (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
        vec.append(val)
    norm = np.linalg.norm(vec)
    return (np.array(vec) / (norm if norm > 0 else 1.0)).tolist()
