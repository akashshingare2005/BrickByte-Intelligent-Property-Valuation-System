from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import binascii
import hashlib
import re
import secrets
from typing import Any

import bcrypt
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from .connection import get_password_reset_collection, get_users_collection


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{7,20}$")


class MongoAuthError(RuntimeError):
    """Raised when a MongoDB-backed authentication operation fails."""


@dataclass
class SessionUser:
    """Lightweight user object that keeps existing template checks working."""

    id: str | None = None
    full_name: str = ""
    email: str = ""
    phone: str = ""
    created_at: datetime | None = None
    is_authenticated: bool = False

    def __str__(self) -> str:
        return self.full_name or self.email or "Guest"


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_name(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_phone(value: str | None) -> str:
    return (value or "").strip()


def hash_password(raw_password: str) -> str:
    """Hash a password with bcrypt before persisting it to MongoDB."""
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, password_hash: str) -> bool:
    """Compare a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_signup_payload(full_name: str, email: str, phone: str, password: str) -> list[str]:
    """Validate the required signup fields before writing to MongoDB."""
    errors: list[str] = []
    if not full_name:
        errors.append("Full name is required.")
    if not email:
        errors.append("Email is required.")
    elif not EMAIL_PATTERN.match(email):
        errors.append("Enter a valid email address.")
    if phone and not PHONE_PATTERN.match(phone):
        errors.append("Enter a valid phone number.")
    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    return errors


def _serialize_user(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document["_id"]),
        "full_name": document.get("full_name", ""),
        "email": document.get("email", ""),
        "phone": document.get("phone", ""),
        "password_hash": document.get("password_hash", ""),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }


def _deserialize_user(document: dict[str, Any] | None) -> SessionUser:
    if not document:
        return SessionUser()

    return SessionUser(
        id=str(document.get("_id")),
        full_name=document.get("full_name", ""),
        email=document.get("email", ""),
        phone=document.get("phone", ""),
        created_at=document.get("created_at"),
        is_authenticated=True,
    )


def get_user_by_identifier(identifier: str) -> dict[str, Any] | None:
    """Look up a user by email first and then by full name for backward compatibility."""
    cleaned_identifier = (identifier or "").strip()
    if not cleaned_identifier:
        return None

    users = get_users_collection()
    normalized_email = normalize_email(cleaned_identifier)
    user = users.find_one({"email": normalized_email})
    if user:
        return _serialize_user(user)

    user = users.find_one({"full_name": cleaned_identifier})
    if user:
        return _serialize_user(user)

    return None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    email = normalize_email(email)
    if not email:
        return None

    user = get_users_collection().find_one({"email": email})
    return _serialize_user(user) if user else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    try:
        object_id = ObjectId(user_id)
    except (binascii.Error, TypeError, ValueError):
        return None

    user = get_users_collection().find_one({"_id": object_id})
    return _serialize_user(user) if user else None


def create_user(full_name: str, email: str, phone: str, password: str) -> dict[str, Any]:
    """Create a new MongoDB user document after validating uniqueness."""
    full_name = normalize_name(full_name)
    email = normalize_email(email)
    phone = normalize_phone(phone)
    password_hash = hash_password(password)
    now = datetime.now(timezone.utc)

    validation_errors = validate_signup_payload(full_name, email, phone, password)
    if validation_errors:
        raise MongoAuthError(" ".join(validation_errors))

    users = get_users_collection()
    if users.find_one({"email": email}):
        raise MongoAuthError("An account with this email already exists.")

    try:
        result = users.insert_one(
            {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "password_hash": password_hash,
                "created_at": now,
                "updated_at": now,
            }
        )
    except DuplicateKeyError as exc:
        raise MongoAuthError("An account with this email already exists.") from exc
    except PyMongoError as exc:
        raise MongoAuthError(f"Unable to create account: {exc}") from exc

    created_user = users.find_one({"_id": result.inserted_id})
    if not created_user:
        raise MongoAuthError("Account was created, but it could not be reloaded.")
    return _serialize_user(created_user)


def authenticate_user(identifier: str, password: str) -> dict[str, Any] | None:
    """Validate credentials against the MongoDB user collection."""
    user = get_user_by_identifier(identifier)
    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None
    return user


def update_user_profile(user_id: str, *, full_name: str | None = None, email: str | None = None, phone: str | None = None) -> dict[str, Any]:
    """Update the logged-in user's profile fields in MongoDB."""
    user = get_user_by_id(user_id)
    if not user:
        raise MongoAuthError("Logged-in user was not found.")

    updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if full_name is not None:
        normalized_full_name = normalize_name(full_name)
        if not normalized_full_name:
            raise MongoAuthError("Full name cannot be empty.")
        updates["full_name"] = normalized_full_name

    if phone is not None:
        normalized_phone = normalize_phone(phone)
        if normalized_phone and not PHONE_PATTERN.match(normalized_phone):
            raise MongoAuthError("Enter a valid phone number.")
        updates["phone"] = normalized_phone

    if email is not None:
        normalized_email = normalize_email(email)
        if not normalized_email or not EMAIL_PATTERN.match(normalized_email):
            raise MongoAuthError("Enter a valid email address.")
        existing_user = get_users_collection().find_one({"email": normalized_email, "_id": {"$ne": ObjectId(user_id)}})
        if existing_user:
            raise MongoAuthError("That email address is already in use.")
        updates["email"] = normalized_email

    if len(updates) == 1:
        return user

    try:
        get_users_collection().update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    except PyMongoError as exc:
        raise MongoAuthError(f"Unable to update profile: {exc}") from exc

    refreshed_user = get_users_collection().find_one({"_id": ObjectId(user_id)})
    if not refreshed_user:
        raise MongoAuthError("Profile was updated, but it could not be reloaded.")
    return _serialize_user(refreshed_user)


def set_session_user(request, user: dict[str, Any]) -> None:
    """Persist the MongoDB user identity in the Django session."""
    request.session["mongo_user_id"] = user["id"]
    request.session["mongo_user_full_name"] = user.get("full_name", "")
    request.session["mongo_user_email"] = user.get("email", "")
    request.session["mongo_user_phone"] = user.get("phone", "")
    request.session.modified = True


def clear_session_user(request) -> None:
    """Remove all authentication data from the current session."""
    for key in ("mongo_user_id", "mongo_user_full_name", "mongo_user_email", "mongo_user_phone"):
        request.session.pop(key, None)
    request.session.modified = True


def get_session_user(request) -> SessionUser:
    """Rehydrate the current user from session data and MongoDB."""
    user_id = request.session.get("mongo_user_id")
    if not user_id:
        return SessionUser()

    user = get_user_by_id(user_id)
    if not user:
        clear_session_user(request)
        return SessionUser()

    return _deserialize_user({"_id": ObjectId(user["id"]), **user})


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_token(email: str) -> str:
    """Create a temporary password reset token stored in MongoDB."""
    normalized_email = normalize_email(email)
    user = get_user_by_email(normalized_email)
    if not user:
        raise MongoAuthError("No account found with this email.")

    reset_token = secrets.token_urlsafe(32)
    reset_document = {
        "email": normalized_email,
        "token_hash": _hash_reset_token(reset_token),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        get_password_reset_collection().insert_one(reset_document)
    except DuplicateKeyError:
        get_password_reset_collection().delete_many({"email": normalized_email})
        get_password_reset_collection().insert_one(reset_document)
    except PyMongoError as exc:
        raise MongoAuthError(f"Unable to create password reset token: {exc}") from exc

    return reset_token


def consume_password_reset_token(email: str, token: str) -> bool:
    """Check the reset token and mark it as used if it is valid."""
    normalized_email = normalize_email(email)
    token_hash = _hash_reset_token(token)
    now = datetime.now(timezone.utc)
    reset_collection = get_password_reset_collection()

    reset_document = reset_collection.find_one(
        {
            "email": normalized_email,
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": now},
        }
    )
    if not reset_document:
        return False

    try:
        reset_collection.update_one({"_id": reset_document["_id"]}, {"$set": {"used": True}})
    except PyMongoError as exc:
        raise MongoAuthError(f"Unable to finalize password reset: {exc}") from exc

    return True


def update_password(email: str, new_password: str) -> None:
    """Store a fresh bcrypt password hash for the given user email."""
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise MongoAuthError("Email is required.")
    if not new_password or len(new_password) < 8:
        raise MongoAuthError("Password must be at least 8 characters long.")

    password_hash = hash_password(new_password)
    result = get_users_collection().update_one(
        {"email": normalized_email},
        {"$set": {"password_hash": password_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise MongoAuthError("No account found with this email.")
