_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    return _model

def embed_text(text: str):
    """Return a dense vector embedding for the given text.
    The model outputs a 384‑dimensional vector.
    """
    model = get_model()
    return model.encode([text], normalize_embeddings=True)[0]
