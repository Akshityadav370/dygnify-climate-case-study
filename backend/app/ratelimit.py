from slowapi import Limiter
from starlette.requests import Request

ANALYZE_LIMIT = "10/minute"
GEOCODE_LIMIT = "30/minute"
EXPORT_LIMIT = "10/minute"
READ_LIMIT = "60/minute"


def client_ip(request: Request) -> str:
    """Client IP used as the rate-limit key.

    Each trusted proxy appends the address it received the request from to
    X-Forwarded-For, so with N trusted proxies the N-th entry from the right is
    the real client. Entries further left are client-controlled and ignored.
    """
    hops = request.app.state.settings.trusted_proxy_hops
    if hops > 0:
        forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, headers_enabled=False)
