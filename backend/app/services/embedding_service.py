from app.config import settings
from app.services.ai_client import client
from app.services.pinecone_client import replace_module_vectors

CHUNK_MAX_CHARS = 1500
CHUNK_OVERLAP_CHARS = 200


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            for i in range(0, len(paragraph), max_chars - overlap):
                chunks.append(paragraph[i : i + max_chars])
            current = ""

    if current:
        chunks.append(current)

    return chunks


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
        dimensions=settings.openai_embedding_dimensions,
    )
    return [item.embedding for item in response.data]


async def embed_text(text: str) -> list[float]:
    vectors = await embed_texts([text])
    return vectors[0]


async def index_module_content(module_id: int, course_id: int, content: str) -> None:
    chunks = chunk_text(content)
    if not chunks:
        return
    embeddings = await embed_texts(chunks)
    await replace_module_vectors(module_id, course_id, chunks, embeddings)
