"""Per-LLM-call cost/latency instrumentation.

Every real chat-completion or embedding call in the app should go through
`instrumented_chat_completion` / `instrumented_embeddings` (or, for the one
streaming call site, call `record_llm_call` directly once usage is known)
rather than calling the OpenAI client directly — that's what makes
GET /admin/metrics actually reflect reality instead of a guess.
"""

import time

import structlog

from app.database import AsyncSessionLocal
from app.models.llm_call import LLMCall
from app.services.ai_client import get_openai_client

logger = structlog.get_logger()

# USD per 1M tokens. Approximate, point-in-time OpenAI pricing — update here
# if pricing changes; unknown models fall back to $0 (logged, not billed).
PRICING_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
    "text-embedding-ada-002": {"prompt": 0.10, "completion": 0.0},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4": {"prompt": 30.00, "completion": 60.00},
}
_ZERO_PRICING = {"prompt": 0.0, "completion": 0.0}


def compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = PRICING_PER_MILLION_TOKENS.get(model, _ZERO_PRICING)
    return (prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]) / 1_000_000


async def record_llm_call(
    *,
    purpose: str,
    endpoint: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int = 0,
    latency_ms: float,
    cache_hit: bool = False,
    user_id: int | None = None,
    course_id: int | None = None,
    module_id: int | None = None,
) -> None:
    cost_usd = compute_cost_usd(model, prompt_tokens, completion_tokens)
    total_tokens = prompt_tokens + completion_tokens

    logger.info(
        "llm_call",
        purpose=purpose,
        endpoint=endpoint,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=round(cost_usd, 8),
        latency_ms=round(latency_ms, 1),
        cache_hit=cache_hit,
        user_id=user_id,
        course_id=course_id,
        module_id=module_id,
    )

    async with AsyncSessionLocal() as db:
        db.add(
            LLMCall(
                user_id=user_id,
                course_id=course_id,
                module_id=module_id,
                endpoint=endpoint,
                purpose=purpose,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                cache_hit=cache_hit,
            )
        )
        await db.commit()


async def instrumented_chat_completion(
    *,
    purpose: str,
    endpoint: str,
    user_id: int | None = None,
    course_id: int | None = None,
    module_id: int | None = None,
    **create_kwargs,
):
    """Drop-in for `client.chat.completions.create(**create_kwargs)` (non-streaming
    only — the one streaming call site instruments itself, since it needs to
    capture usage from the final chunk after yielding all the deltas)."""
    start = time.perf_counter()
    response = await get_openai_client().chat.completions.create(**create_kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    usage = getattr(response, "usage", None)
    await record_llm_call(
        purpose=purpose,
        endpoint=endpoint,
        model=create_kwargs.get("model", "unknown"),
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
        user_id=user_id,
        course_id=course_id,
        module_id=module_id,
    )
    return response


async def instrumented_embeddings(
    *,
    purpose: str,
    endpoint: str,
    user_id: int | None = None,
    course_id: int | None = None,
    module_id: int | None = None,
    **create_kwargs,
):
    """Drop-in for `client.embeddings.create(**create_kwargs)`."""
    start = time.perf_counter()
    response = await get_openai_client().embeddings.create(**create_kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    usage = getattr(response, "usage", None)
    await record_llm_call(
        purpose=purpose,
        endpoint=endpoint,
        model=create_kwargs.get("model", "unknown"),
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=0,
        latency_ms=latency_ms,
        user_id=user_id,
        course_id=course_id,
        module_id=module_id,
    )
    return response
