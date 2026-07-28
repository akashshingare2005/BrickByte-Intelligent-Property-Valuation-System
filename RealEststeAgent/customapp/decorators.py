from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .mongo.auth import get_session_user


def mongo_login_required(view_func):
    """Require a MongoDB-backed session before entering a protected view."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        user = get_session_user(request)
        if not user.is_authenticated:
            messages.error(request, "Please log in to continue.")
            return redirect("login")

        request.mongo_user = user
        return view_func(request, *args, **kwargs)

    return wrapped_view
