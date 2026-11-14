from django.core.exceptions import ValidationError


def role_of(user):
    return getattr(getattr(user, "staff", None), "role", None)


def require_role(user, *roles):
    """Raise unless `user` is a superuser or holds one of `roles` (StaffProfile.Role values)."""
    if user is not None and (user.is_superuser or role_of(user) in roles):
        return
    raise ValidationError("You do not have permission to do this.")


# Role groups used by views, services and the navigation. Superusers pass every check.
def _roles():
    from apps.core.models import StaffProfile

    R = StaffProfile.Role
    return {
        "ADMINS": (R.ADMIN,),
        "MONEY": (R.FINANCE, R.ADMIN),  # record payments and expenses, issue invoices
        "EVERYONE": (R.STAFF, R.FINANCE, R.ADMIN),
    }


def __getattr__(name):  # lets code write `from apps.core.permissions import MONEY`
    roles = _roles()
    if name in roles:
        return roles[name]
    raise AttributeError(name)
