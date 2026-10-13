from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings


def create_mongo_client(settings: Settings) -> AsyncMongoClient:
    return AsyncMongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def ensure_indexes(db: AsyncDatabase) -> None:
    # TTL indexes: MongoDB deletes documents once `expires_at` is in the past.
    await db.analyses.create_index("expires_at", expireAfterSeconds=0)
    await db.geocode_cache.create_index("expires_at", expireAfterSeconds=0)
