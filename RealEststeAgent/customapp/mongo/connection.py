from functools import lru_cache
import os

from django.conf import settings
from pymongo import MongoClient
from pymongo.errors import PyMongoError


class MongoConfigurationError(RuntimeError):
    """Raised when the MongoDB Atlas connection is not configured correctly."""


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """Create a cached MongoDB client using the Atlas connection string."""
    mongo_uri = getattr(settings, "MONGO_URI", None) or os.getenv("MONGO_URI")
    if not mongo_uri:
        raise MongoConfigurationError("MONGO_URI is not configured.")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client
    except PyMongoError as exc:
        raise MongoConfigurationError(f"Unable to connect to MongoDB Atlas: {exc}") from exc


@lru_cache(maxsize=1)
def get_mongo_database():
    """Return the BrickByte database handle."""
    database_name = getattr(settings, "MONGO_DB_NAME", None) or os.getenv("MONGO_DB_NAME", "BrickByteDB")
    return get_mongo_client()[database_name]


@lru_cache(maxsize=1)
def ensure_mongo_indexes() -> None:
    """Create the indexes needed for fast lookups and duplicate prevention."""
    database = get_mongo_database()
    users = database[getattr(settings, "MONGO_USERS_COLLECTION", "users")]
    users.create_index("email", unique=True)
    users.create_index("full_name")
    users.create_index("phone")

    reset_tokens = database[getattr(settings, "MONGO_PASSWORD_RESET_COLLECTION", "password_reset_tokens")]
    reset_tokens.create_index("token_hash", unique=True)
    reset_tokens.create_index("expires_at", expireAfterSeconds=0)


def get_users_collection():
    """Return the MongoDB collection used to store BrickByte users."""
    ensure_mongo_indexes()
    return get_mongo_database()[getattr(settings, "MONGO_USERS_COLLECTION", "users")]


def get_password_reset_collection():
    """Return the collection that stores temporary password reset tokens."""
    ensure_mongo_indexes()
    return get_mongo_database()[getattr(settings, "MONGO_PASSWORD_RESET_COLLECTION", "password_reset_tokens")]
