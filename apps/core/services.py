from django.contrib.auth import get_user_model
from django.db import transaction

from apps.core.async_utils import service
from apps.core.models import StaffProfile
from apps.core.permissions import require_role

from .invites import send_invite

Role = StaffProfile.Role


@service
@transaction.atomic
def create_staff(by, *, email, first_name, base_url, last_name="", role=Role.STAFF, title="", phone="", is_director=False):
    """Add a person who can sign in, with their role. They get an email with a link to choose their own password
    (sent once the save has gone through), so nobody else ever knows it."""
    require_role(by, Role.ADMIN)
    User = get_user_model()
    user = User(email=User.objects.normalize_email(email), first_name=first_name, last_name=last_name)
    user.set_unusable_password()
    user.save()
    profile = StaffProfile.objects.create(user=user, role=role, title=title, phone=phone, is_director=is_director)
    transaction.on_commit(lambda: send_invite(profile, base_url=base_url, invited_by=by))
    return profile


@service
def resend_invite(profile, by, *, base_url):
    """A fresh set-password link, for someone whose first one expired or got lost."""
    require_role(by, Role.ADMIN)
    profile = StaffProfile.objects.select_related("user").get(pk=profile.pk)
    send_invite(profile, base_url=base_url, invited_by=by)
    return profile
