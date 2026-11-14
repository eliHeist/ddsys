from django.contrib.auth import get_user_model
from django.db import transaction

from apps.core.async_utils import service
from apps.core.models import StaffProfile
from apps.core.permissions import require_role

Role = StaffProfile.Role


@service
@transaction.atomic
def create_staff(by, *, email, password, first_name, last_name="", role=Role.STAFF, title="", phone=""):
    """Add a person who can sign in, with their role."""
    require_role(by, Role.ADMIN)
    user = get_user_model().objects.create_user(email, password=password, first_name=first_name, last_name=last_name)
    return StaffProfile.objects.create(user=user, role=role, title=title, phone=phone)
