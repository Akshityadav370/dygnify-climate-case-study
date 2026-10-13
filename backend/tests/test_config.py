import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "raw",
    [
        "https://a.vercel.app,https://b.vercel.app",
        " https://a.vercel.app , https://b.vercel.app ",
        '["https://a.vercel.app", "https://b.vercel.app"]',
    ],
)
def test_cors_origins_accepts_comma_separated_or_json(monkeypatch, raw):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == ["https://a.vercel.app", "https://b.vercel.app"]


def test_cors_origins_single_url_and_trailing_slash(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app/")
    assert Settings(_env_file=None).cors_origins == ["https://a.vercel.app"]
