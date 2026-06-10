"""Generate text embeddings via DashScope (OpenAI-compatible) and upsert to Qdrant."""

import uuid

from jobcopilot_shared.logging import get_logger

from app.config import settings

logger = get_logger(__name__)


async def embed_and_upsert(resume_id: uuid.UUID, user_id: uuid.UUID, text: str) -> bool:
    """Compute embedding and upsert to Qdrant. Returns False if skipped (no API key)."""
    if not settings.dashscope_api_key:
        logger.info("embedding_skipped", reason="DASHSCOPE_API_KEY not set")
        return False
    if not text.strip():
        logger.info("embedding_skipped", reason="empty text")
        return False

    vector = await _get_embedding(text)
    if not vector:
        return False

    await _upsert_to_qdrant(resume_id, user_id, vector)
    return True


async def delete_embedding(resume_id: uuid.UUID) -> None:
    """Remove a resume's vector from Qdrant."""
    if not settings.dashscope_api_key:
        return
    try:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(url=settings.qdrant_url)
        await client.delete(
            collection_name=settings.qdrant_resume_collection,
            points_selector=[str(resume_id)],
        )
    except Exception as exc:
        logger.warning("qdrant_delete_failed", resume_id=str(resume_id), error=str(exc))


async def _get_embedding(text: str) -> list[float] | None:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )
        # Truncate to ~8000 tokens to stay within model limits
        truncated = text[: 8000 * 4]
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=truncated,
            dimensions=settings.embedding_dimensions,
        )
        return response.data[0].embedding
    except Exception as exc:
        logger.error("embedding_failed", error=str(exc))
        return None


async def _upsert_to_qdrant(
    resume_id: uuid.UUID, user_id: uuid.UUID, vector: list[float]
) -> None:
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams

        client = AsyncQdrantClient(url=settings.qdrant_url)

        # Ensure collection exists
        collections = await client.get_collections()
        names = [c.name for c in collections.collections]
        if settings.qdrant_resume_collection not in names:
            await client.create_collection(
                collection_name=settings.qdrant_resume_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )

        await client.upsert(
            collection_name=settings.qdrant_resume_collection,
            points=[
                PointStruct(
                    id=str(resume_id),
                    vector=vector,
                    payload={"user_id": str(user_id)},
                )
            ],
        )
        logger.info("qdrant_upserted", resume_id=str(resume_id))
    except Exception as exc:
        logger.error("qdrant_upsert_failed", resume_id=str(resume_id), error=str(exc))
