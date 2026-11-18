"""The welcome email a new staff member gets: who added them, what they can do, and a link to choose their own
password (allauth's password-reset link, so it expires and works once). Admins never set or see passwords."""
from urllib.parse import urljoin

from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from apps.core.models import CompanySettings

WHAT_ROLES_DO = {
    "admin": "everything, including staff, accounts and company settings",
    "finance": "quotations, invoices, payments, expenses, loans and the accounts",
    "staff": "clients, projects, quotations and draft invoices",
}


def set_password_link(user, base_url):
    """A one-time link to choose a password (valid for PASSWORD_RESET_TIMEOUT, three days by default)."""
    path = reverse("account_reset_password_from_key",
                   kwargs={"uidb36": user_pk_to_url_str(user), "key": default_token_generator.make_token(user)})
    return urljoin(base_url, path)


def send_invite(profile, *, base_url, invited_by=None):
    user, company = profile.user, CompanySettings.load()
    context = {
        "name": user.first_name or user.email, "email": user.email, "company": company.name,
        "role": profile.get_role_display(), "can_do": WHAT_ROLES_DO.get(profile.role, ""), "title": profile.title,
        "is_director": profile.is_director,
        "invited_by": (invited_by.get_full_name() or invited_by.email) if invited_by else company.name,
        "set_password_url": set_password_link(user, base_url),
        "sign_in_url": urljoin(base_url, reverse("account_login")),
        "security_url": urljoin(base_url, reverse("mfa_index")),
        "days": max(1, settings.PASSWORD_RESET_TIMEOUT // 86400),
    }
    message = EmailMultiAlternatives(
        subject=f"Your {company.name} account: choose your password",
        body=render_to_string("core/emails/staff_invite.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email],
    )
    message.attach_alternative(render_to_string("core/emails/staff_invite.html", context), "text/html")
    message.send()
