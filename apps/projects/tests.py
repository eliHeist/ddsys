"""Project secrets: stored encrypted, values only through the logged endpoint, admins alone delete."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import StaffProfile

from .dotenv import env_line
from .models import Project, ProjectSecret, SecretReveal


class SecretTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user("admin@dakdot.com", password="x" * 12)
        StaffProfile.objects.create(user=cls.admin, role=StaffProfile.Role.ADMIN)
        cls.staff = User.objects.create_user("staff@dakdot.com", password="x" * 12)
        StaffProfile.objects.create(user=cls.staff, role=StaffProfile.Role.STAFF)
        cls.project = Project.objects.create(title="School SaaS", kind=Project.Kind.PRODUCT, code="school-saas")
        cls.key = ProjectSecret(project=cls.project, title="Stripe key", name="STRIPE_SECRET_KEY")
        cls.key.value = "sk_live_123"
        cls.key.save()

    def url(self, name, *args):
        return reverse(f"projects:{name}", args=[self.project.pk, *args])

    def test_value_is_encrypted_in_the_database(self):
        stored = ProjectSecret.objects.values_list("encrypted_value", flat=True).get()
        self.assertNotIn("sk_live_123", stored)
        self.assertEqual(ProjectSecret.objects.get().value, "sk_live_123")

    def test_project_page_lists_secret_without_its_value(self):
        self.client.force_login(self.staff)
        page = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertContains(page, "STRIPE_SECRET_KEY")
        self.assertNotContains(page, "sk_live_123")

    def test_reveal_returns_value_and_is_logged(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url("secret-value", self.key.pk), {"action": "copy"})
        self.assertEqual(response.json(), {"value": "sk_live_123"})
        self.assertEqual(response["Cache-Control"], "no-store")
        reveal = SecretReveal.objects.get()
        self.assertEqual((reveal.user, reveal.action), (self.staff, SecretReveal.Action.COPY))
        self.assertEqual(self.client.get(self.url("secret-value", self.key.pk)).status_code, 405)

    def test_add_login_and_edit_keeps_password_when_left_empty(self):
        self.client.force_login(self.staff)
        self.client.post(self.url("secret-new") + "?kind=login", {
            "title": "Django admin", "name": "elijah", "value": "p@ss word", "link": "https://app.example.com/admin/"})
        login = ProjectSecret.objects.get(kind=ProjectSecret.Kind.LOGIN)
        self.assertEqual((login.name, login.value, login.created_by), ("elijah", "p@ss word", self.staff))
        self.client.post(self.url("secret-edit", login.pk), {"title": "Django admin", "name": "elijah2", "value": "", "link": ""})
        login.refresh_from_db()
        self.assertEqual((login.name, login.value), ("elijah2", "p@ss word"))

    def test_variable_names_are_unique_per_project(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url("secret-new") + "?kind=variable",
                                    {"title": "Again", "name": "STRIPE_SECRET_KEY", "value": "x"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(ProjectSecret.objects.count(), 1)

    def test_env_export(self):
        other = ProjectSecret(project=self.project, title="Greeting", name="GREETING")
        other.value = 'say "hi"\nbye'
        other.save()
        self.client.force_login(self.staff)
        text = self.client.post(self.url("secrets-env")).json()["value"]
        self.assertEqual(text, 'GREETING="say \\"hi\\"\\nbye"\nSTRIPE_SECRET_KEY=sk_live_123\n')
        self.assertEqual(SecretReveal.objects.filter(action=SecretReveal.Action.EXPORT).count(), 2)
        self.assertEqual(env_line("URL", "postgres://u:p@h/db"), "URL=postgres://u:p@h/db")

    def test_only_admins_delete(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.url("secret-delete", self.key.pk)).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(self.url("secret-delete", self.key.pk))
        self.assertFalse(ProjectSecret.objects.exists())
