from collections.abc import AsyncGenerator
from typing import Any

from app.config import settings
from app.models.module import Module
from app.services.ai_client import client
from app.services.embedding_service import embed_text
from app.services.pinecone_client import query_module_context
from app.services.redis_client import doubt_cache_key, get_cached_doubt, set_cached_doubt


def build_system_prompt(module: Module, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context was retrieved."
    return (
        f"You are a helpful teaching assistant answering a learner's question about the module "
        f"'{module.title}'. Use the following retrieved excerpts from the module content as your "
        "primary source of truth. If the excerpts don't contain the answer, say so honestly instead "
        f"of making things up.\n\nRetrieved context:\n{context}"
    )


async def stream_chat_answer(
    module: Module, question: str, context_chunks: list[str]
) -> AsyncGenerator[str, None]:
    stream = await client.chat.completions.create(
        model=settings.openai_chat_model,
        stream=True,
        temperature=0.3,
        messages=[
            {"role": "system", "content": build_system_prompt(module, context_chunks)},
            {"role": "user", "content": question},
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def resolve_doubt(module: Module, question: str) -> AsyncGenerator[dict[str, Any], None]:
    """Yields {"type": "chunk", "delta": str} events followed by one terminal
    {"type": "done", "answer": str, "cache_hit": bool, "retrieved_chunk_ids": list} event."""
    embedding = await embed_text(question)
    cache_key = doubt_cache_key(module.id, question)

    cached = await get_cached_doubt(cache_key)
    if cached is not None:
        yield {"type": "chunk", "delta": cached["answer"]}
        yield {
            "type": "done",
            "answer": cached["answer"],
            "cache_hit": True,
            "retrieved_chunk_ids": cached.get("retrieved_chunk_ids", []),
        }
        return

    matches = await query_module_context(module.id, embedding, settings.doubt_retrieval_top_k)
    context_chunks = [match["text"] for match in matches]
    retrieved_chunk_ids = [match["id"] for match in matches]

    answer_parts: list[str] = []
    async for delta in stream_chat_answer(module, question, context_chunks):
        answer_parts.append(delta)
        yield {"type": "chunk", "delta": delta}

    answer = "".join(answer_parts)
    await set_cached_doubt(cache_key, {"answer": answer, "retrieved_chunk_ids": retrieved_chunk_ids})

    yield {
        "type": "done",
        "answer": answer,
        "cache_hit": False,
        "retrieved_chunk_ids": retrieved_chunk_ids,
    }
