from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def secrets_key_set(app_configs, **kwargs):
    """`manage.py check --deploy` fails until SECRETS_KEY is set, so project secrets never use the fallback key."""
    if not settings.SECRETS_KEY:
        return [Error("SECRETS_KEY is not set.", hint="Run `uv run manage.py secrets_key` and put the result in dakdot/.env.",
                      id="dakdot.E001")]
    return []


@register(Tags.security, deploy=True)
def email_really_sends(app_configs, **kwargs):
    """Staff invites and password resets are emails: with the console backend they would only reach the log."""
    if "console" in settings.EMAIL_BACKEND or "locmem" in settings.EMAIL_BACKEND or "dummy" in settings.EMAIL_BACKEND:
        return [Error("Email is not set up: staff invites and password resets would never arrive.",
                      hint="Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend and EMAIL_HOST, "
                           "EMAIL_HOST_USER, EMAIL_HOST_PASSWORD in dakdot/.env.", id="dakdot.E002")]
    return []
