from .mongo.auth import get_session_user


def mongo_user_context(request):
    """Expose the MongoDB-backed user object as `user` for unchanged templates."""
    return {"user": get_session_user(request)}
