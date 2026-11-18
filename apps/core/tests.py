"""Adding staff: no password is typed by the admin; the new person gets an email with a link to choose one."""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import StaffProfile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StaffInviteTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("admin@dakdot.com", password="x" * 12, first_name="Elijah")
        StaffProfile.objects.create(user=self.admin, role=StaffProfile.Role.ADMIN)
        self.client.force_login(self.admin)

    def add(self):
        return self.client.post(reverse("core:staff-new"), {
            "first_name": "Grace", "last_name": "Akello", "email": "Grace@Dakdot.com", "role": "finance",
            "title": "Accountant", "phone": "", "is_director": "on"}, headers={"HX-Request": "true"})

    def test_new_staff_get_an_email_and_can_choose_a_password(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.add()
        self.assertEqual(response.status_code, 204, response.content)
        grace = get_user_model().objects.get(email__iexact="grace@dakdot.com")
        self.assertFalse(grace.has_usable_password())
        self.assertTrue(grace.staff.is_director)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["grace@dakdot.com"])
        for detail in ("Grace", "Finance", "Accountant", "grace@dakdot.com", "Elijah", "/accounts/login/", "two-factor"):
            self.assertIn(detail, email.body)
        link = re.search(r"http://testserver(/accounts/password/reset/key/\S+)", email.body).group(1)

        self.client.logout()
        page = self.client.get(link, follow=True)  # allauth swaps the key for a session and redirects
        self.assertEqual(page.status_code, 200)
        self.client.post(page.redirect_chain[-1][0] if page.redirect_chain else link,
                         {"password1": "a-long-new-password-9", "password2": "a-long-new-password-9"})
        grace.refresh_from_db()
        self.assertTrue(grace.check_password("a-long-new-password-9"))

    def test_send_a_new_link(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.add()
        grace = StaffProfile.objects.get(user__email__iexact="grace@dakdot.com")
        self.client.post(reverse("core:staff-invite", args=[grace.pk]), headers={"HX-Request": "true"})
        self.assertEqual(len(mail.outbox), 2)


class MediaTests(TestCase):
    def test_uploads_are_for_signed_in_staff_only(self):
        from django.conf import settings
        from pathlib import Path
        folder = Path(settings.MEDIA_ROOT) / "test"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "receipt.txt").write_text("paid")
        try:
            url = "/media/test/receipt.txt"
            self.assertEqual(self.client.get(url).status_code, 302)  # to the sign-in page
            user = get_user_model().objects.create_user("a@dakdot.com", password="x" * 12)
            StaffProfile.objects.create(user=user, role=StaffProfile.Role.STAFF)
            self.client.force_login(user)
            self.assertEqual(b"".join(self.client.get(url).streaming_content), b"paid")
            self.assertEqual(self.client.get("/media/../dakdot/settings.py").status_code, 404)
        finally:
            (folder / "receipt.txt").unlink()
            folder.rmdir()
