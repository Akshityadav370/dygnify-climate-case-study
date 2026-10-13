import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import Settings
from app.main import create_app
from app.ratelimit import limiter

TEST_DB = "climate_hazards_test"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        mongo_db=TEST_DB,
        http_backoff_seconds=0,
        http_retries=1,
        cors_origins=["http://allowed.test"],
    )


@pytest.fixture
def mongo(settings):
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
    client.drop_database(TEST_DB)
    yield client[TEST_DB]
    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def client(settings, mongo):
    limiter.reset()
    with TestClient(create_app(settings)) as test_client:
        yield test_client
