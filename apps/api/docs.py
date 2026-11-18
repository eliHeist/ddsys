from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from apps.core.permissions import role_of


def admins_only(view):
    """The API docs page: signed-in admins only (it lists every endpoint and lets you try them)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_superuser or role_of(user) == "admin"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
