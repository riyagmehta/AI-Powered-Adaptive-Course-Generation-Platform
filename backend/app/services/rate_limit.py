from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.services.security import decode_access_token


def rate_limit_key(request: Request) -> str:
    """Key by authenticated user when possible, so limits track a person
    rather than an IP shared by a NAT/office/dev network. Falls back to the
    remote address for unauthenticated requests."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        payload = decode_access_token(auth_header.removeprefix("Bearer "))
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, storage_uri=settings.redis_url)
