from __future__ import annotations
from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse
from ..auth import get_optional_user
from ..rate_limiter import RateLimiter
from ..services.retrieval import hybrid_retrieve
from ..services.model_router import choose_model
from ..services.openai_llm import stream_completion
from ..config import settings
from ..usage import AnonymousUsageGate, resolve_guest_key


router = APIRouter(prefix="/ask", tags=["ask"])
rate = RateLimiter()
guest_usage = AnonymousUsageGate()


SYSTEM_PROMPT = (
    "Answer succinctly in <=120 words. Quote rule names only, not text. "
    "Every factual claim must include an inline citation placeholder like [[c0]], [[c1]]. "
    "If unsure, reply 'uncertain'."
)


@router.get("/stream")
async def ask_stream(
    request: Request,
    q: str = Query(..., max_length=500),
    game_system_id: int = Query(...),
    user=Depends(get_optional_user),
):
    await rate.init()
    guest_key = resolve_guest_key(request)
    rate_key = f"ask:user:{user.id}" if user else f"ask:guest:{guest_key}"
    await rate.check(rate_key)
    reservation = None
    if user is None:
        reservation = await guest_usage.reserve(guest_key, q)

    chunks = await hybrid_retrieve(user.id if user else None, game_system_id, q, k=8)
    retrieval_score = 0.6 if chunks else 0.0 # TODO: compute properly
    conflicts = 0 # TODO: detect conflicting snippets
    model = choose_model(settings.FEATURE_AUTO_ESCALATE, retrieval_score, len(q), conflicts)


    async def event_gen():
        streamed_text = ""
        try:
            async for delta in stream_completion(model, SYSTEM_PROMPT, q, chunks):
                streamed_text += delta
                yield {"event": "token", "data": delta}
        finally:
            if user is None:
                await guest_usage.finalize(guest_key, reservation, streamed_text)
        yield {"event": "done", "data": "{}"}


    return EventSourceResponse(event_gen())
