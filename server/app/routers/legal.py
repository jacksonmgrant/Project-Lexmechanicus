from __future__ import annotations

from fastapi import APIRouter

from ..config import settings


router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/info")
async def get_legal_info():
    return {
        "service_provider": {
            "legal_name": settings.SERVICE_PROVIDER_LEGAL_NAME,
            "address": settings.SERVICE_PROVIDER_ADDRESS or None,
            "alternate_names": settings.SERVICE_PROVIDER_ALT_NAMES,
        },
        "dmca_agent": {
            "name": settings.DMCA_DESIGNATED_AGENT_NAME or None,
            "organization": settings.DMCA_DESIGNATED_AGENT_ORGANIZATION or None,
            "email": settings.DMCA_DESIGNATED_AGENT_EMAIL or None,
            "phone": settings.DMCA_DESIGNATED_AGENT_PHONE or None,
            "address": settings.DMCA_DESIGNATED_AGENT_ADDRESS or None,
            "configured": bool(
                settings.DMCA_DESIGNATED_AGENT_NAME
                and settings.DMCA_DESIGNATED_AGENT_EMAIL
                and settings.DMCA_DESIGNATED_AGENT_ADDRESS
            ),
        },
        "repeat_infringer_threshold": settings.DMCA_REPEAT_INFRINGER_THRESHOLD,
        "terms_version": settings.TERMS_VERSION,
        "last_updated": settings.LEGAL_POLICY_LAST_UPDATED,
    }
