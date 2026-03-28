from __future__ import annotations
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sse_starlette.sse import EventSourceResponse
from ..auth import get_optional_user
from ..db import SessionLocal
from ..errors import error_detail, raise_api_error
from ..rate_limiter import RateLimiter
from ..services.bundles import load_accessible_bundle
from ..services.citations import build_chat_citations
from ..services.retrieval import hybrid_retrieve
from ..services.rulesets import get_ruleset_scope_ids
from ..services.model_router import choose_model
from ..services.openai_llm import stream_completion
from ..config import settings
from ..usage import AnonymousUsageGate, resolve_guest_key


router = APIRouter(prefix="/ask", tags=["ask"])
rate = RateLimiter()
guest_usage = AnonymousUsageGate()
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "Answer succinctly in <=120 words using the retrieved snippets as your primary evidence. "
    "Synthesize the best direct answer you can from relevant snippets, even if they are partial excerpts. "
    "Only reply 'uncertain' when the retrieved snippets do not answer the user's core question or directly conflict. "
    "Quote rule names only, not rule text. "
    "Every factual claim must include an inline citation placeholder like [[c0]], [[c1]]."
)


@router.get("/stream")
async def ask_stream(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    ruleset_id: int = Query(..., ge=1),
    bundle_id: int | None = Query(None, ge=1),
    user=Depends(get_optional_user),
):
    question = q.strip()
    if not question:
        raise_api_error(422, "Enter a question before sending.", "QUESTION_REQUIRED")

    await rate.init()
    guest_key = resolve_guest_key(request)
    rate_key = f"ask:user:{user.id}" if user else f"ask:guest:{guest_key}"
    await rate.check(rate_key)
    reservation = None
    if user is None:
        reservation = await guest_usage.reserve(guest_key, question)

    try:
        async with SessionLocal() as db:
            _, scoped_ruleset_ids = await get_ruleset_scope_ids(db, ruleset_id=ruleset_id)
            selected_bundle = None
            if bundle_id is not None:
                selected_bundle = await load_accessible_bundle(
                    db,
                    bundle_id=bundle_id,
                    user_id=user.id if user else None,
                    ruleset_id=ruleset_id,
                )
        if scoped_ruleset_ids == []:
            raise_api_error(422, "Choose a valid game system.", "RULESET_NOT_FOUND")
        if scoped_ruleset_ids is None:
            raise_api_error(422, "Choose a game system before chatting.", "RULESET_REQUIRED")
        if bundle_id is not None and selected_bundle is None:
            raise_api_error(422, "Choose a valid bundle for that game system.", "BUNDLE_NOT_FOUND")
        chunks = await hybrid_retrieve(
            user.id if user else None,
            ruleset_ids=scoped_ruleset_ids,
            include_all=False,
            query=question,
            k=8,
            bundle_id=selected_bundle.id if selected_bundle else None,
        )
    except SQLAlchemyError:
        logger.exception(
            "Ask retrieval failed",
            extra={
                "ruleset_id": ruleset_id,
                "bundle_id": bundle_id,
                "user_id": user.id if user else None,
            },
        )
        raise_api_error(503, "Search is temporarily unavailable. Please try again.", "RETRIEVAL_UNAVAILABLE")
    try:
        citations = await build_chat_citations(chunks)
    except Exception:
        logger.warning(
            "Failed to build chat citations",
            extra={"ruleset_id": ruleset_id, "bundle_id": bundle_id, "user_id": user.id if user else None},
        )
        citations = []
    retrieval_score = 0.6 if chunks else 0.0 # TODO: compute properly
    conflicts = 0 # TODO: detect conflicting snippets
    model = choose_model(settings.FEATURE_AUTO_ESCALATE, retrieval_score, len(question), conflicts)


    async def event_gen():
        streamed_text = ""
        if citations:
            yield {"event": "citations", "data": json.dumps({"citations": citations})}
        try:
            async for delta in stream_completion(model, SYSTEM_PROMPT, question, chunks):
                streamed_text += delta
                yield {"event": "token", "data": delta}
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else error_detail(str(exc.detail), "STREAM_FAILED")
            logger.warning("Streaming request failed", extra={"user_id": user.id if user else None, "ruleset_id": ruleset_id, "code": detail.get("code")})
            yield {"event": "error", "data": json.dumps(detail)}
        except Exception:
            logger.exception("Streaming request failed unexpectedly", extra={"user_id": user.id if user else None, "ruleset_id": ruleset_id})
            yield {"event": "error", "data": json.dumps(error_detail("The response stream was interrupted. Please try again.", "STREAM_INTERRUPTED"))}
        finally:
            if user is None:
                try:
                    await guest_usage.finalize(guest_key, reservation, streamed_text)
                except Exception:
                    logger.warning("Failed to finalize guest usage", extra={"ruleset_id": ruleset_id})
        yield {"event": "done", "data": "{}"}


    return EventSourceResponse(event_gen())
