"""Internal API key authentication для service-to-service calls.

Per N10 research: shared-secret в `X-Internal-Key` header for internal docker network.
Validated з constant-time compare to prevent timing attacks.
"""

import hmac

from fastapi import Header, HTTPException, status

from ai_agent_system.config import settings


async def require_internal_auth(
    x_internal_key: str | None = Header(default=None),
) -> None:
    """FastAPI dependency: require valid internal API key.

    Use as: `dependencies=[Depends(require_internal_auth)]` on routes.
    """
    expected = settings.internal_api_key.get_secret_value()
    if not x_internal_key or not hmac.compare_digest(x_internal_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-Internal-Key header",
        )
