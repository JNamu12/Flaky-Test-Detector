import os
from datetime import datetime
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from .embeddings import embed_text

_client = None

def get_qdrant_client():
    global _client
    if _client is None:
        QDRANT_URL = os.getenv("QDRANT_URL", "")
        QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
        if QDRANT_URL:
            _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)
        else:
            BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            QDRANT_PATH = os.path.join(BASE_DIR, "qdrant_data")
            try:
                _client = QdrantClient(path=QDRANT_PATH)
            except Exception:
                _client = QdrantClient(location=":memory:")
    return _client

class _ClientProxy:
    def __getattr__(self, name):
        return getattr(get_qdrant_client(), name)

client = _ClientProxy()

COLLECTION_NAME = "test_failures"
VECTOR_SIZE = 384  # BGE small model output dimension

def ensure_collection():
    """Create the collection if it does not already exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


import uuid

def upsert_failure(test_name: str, error_message: str, stack_trace: str | None, timestamp: datetime):
    """Insert or update a failure record in Qdrant.

    The payload stores the test metadata; the vector is derived from a
    concatenation of the error message and optional stack trace.
    """
    ensure_collection()
    # Build a unique payload ID – generate a deterministic UUID5 using the test name and timestamp
    unique_str = f"{test_name}:{timestamp.isoformat()}"
    payload_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_str))
    text = error_message if not stack_trace else f"{error_message}\n{stack_trace}"
    vector = embed_text(text).tolist()
    point = PointStruct(id=payload_id, payload={
        "test_name": test_name,
        "error_message": error_message,
        "stack_trace": stack_trace or "",
        "timestamp": timestamp.isoformat(),
    }, vector=vector)
    client.upsert(collection_name=COLLECTION_NAME, points=[point])

def search_similar_failures(error_message: str, stack_trace: str | None = None, top_k: int = 5) -> List[dict]:
    """Search for the most similar failure records.

    Returns a list of payload dictionaries sorted by similarity.
    """
    ensure_collection()
    query_text = error_message if not stack_trace else f"{error_message}\n{stack_trace}"
    query_vector = embed_text(query_text).tolist()
    if hasattr(client, "query_points"):
        res = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        return [hit.payload for hit in res.points]
    else:
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        return [hit.payload for hit in results]
