from types import SimpleNamespace

from starlette.requests import Request

from app.ratelimit import client_ip


def make_request(hops: int, forwarded: str | None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(trusted_proxy_hops=hops)))
    scope = {"type": "http", "headers": headers, "client": (peer, 1234), "app": app}
    return Request(scope)


def test_client_ip_uses_peer_when_no_trusted_proxy():
    assert client_ip(make_request(0, "1.2.3.4")) == "10.0.0.1"


def test_client_ip_ignores_spoofed_left_entries():
    # Client sent "6.6.6.6"; the trusted proxy appended the real address.
    assert client_ip(make_request(1, "6.6.6.6, 203.0.113.9")) == "203.0.113.9"


def test_client_ip_falls_back_to_peer_when_header_too_short():
    assert client_ip(make_request(2, "203.0.113.9")) == "10.0.0.1"


def test_rate_limit_returns_429_with_retry_after(client):
    for _ in range(60):
        assert client.get("/api/hazards").status_code == 200
    response = client.get("/api/hazards")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/api/analyze",
        headers={"Origin": "http://allowed.test", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://allowed.test"
    blocked = client.options(
        "/api/analyze",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_large_responses_are_gzipped(client):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("content-encoding") == "gzip"
