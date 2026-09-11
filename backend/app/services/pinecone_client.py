import asyncio
from functools import lru_cache
from typing import Any

from pinecone import Pinecone

from app.config import settings


@lru_cache
def _get_index():
    """Constructed lazily and cached, not at import time — `Pinecone(api_key=...)`
    raises immediately if the key is missing/blank (e.g. in CI, which has no real
    Pinecone credentials), so building it eagerly at module scope meant merely
    importing this module required live credentials."""
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc.Index(settings.pinecone_index_name)


def _module_namespace(module_id: int) -> str:
    return f"module-{module_id}"


async def replace_module_vectors(
    module_id: int,
    course_id: int,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    namespace = _module_namespace(module_id)
    index = _get_index()

    try:
        await asyncio.to_thread(index.delete, delete_all=True, namespace=namespace)
    except Exception as exc:
        if "Namespace not found" not in str(exc):
            raise

    vectors = [
        {
            "id": f"module-{module_id}-chunk-{i}",
            "values": embedding,
            "metadata": {
                "module_id": module_id,
                "course_id": course_id,
                "chunk_index": i,
                "text": chunk,
            },
        }
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    if vectors:
        await asyncio.to_thread(index.upsert, vectors=vectors, namespace=namespace)


async def query_module_context(
    module_id: int,
    embedding: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    namespace = _module_namespace(module_id)
    result = await asyncio.to_thread(
        _get_index().query,
        vector=embedding,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True,
    )

    return [
        {
            "id": match["id"],
            "score": match["score"],
            "text": match["metadata"].get("text", ""),
            "chunk_index": match["metadata"].get("chunk_index"),
        }
        for match in result.get("matches", [])
    ]
