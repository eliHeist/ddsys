from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.api.services import create_api_key, revoke_api_key
from apps.billing.models import Invoice
from apps.billing.services import invoices, receipts, subscriptions
from apps.clients.models import Client
from apps.core.models import StaffProfile
from apps.finance.models import Account
from apps.projects.models import Project

PLAN = [{"description": "Standard plan", "unit_price": "150000"}]


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user("admin@dakdot.com", password="x" * 12)
        StaffProfile.objects.create(user=cls.admin, role=StaffProfile.Role.ADMIN)
        cls.product = Project.objects.create(title="School SaaS", kind=Project.Kind.PRODUCT, code="school-saas")
        cls.other = Project.objects.create(title="Gearhouse", kind=Project.Kind.PRODUCT, code="gearhouse")
        cls.school = Client.objects.create(name="Olympus Pre-school", email="head@olympus.ug")
        cls.garage = Client.objects.create(name="Mechbrif")
        cls.momo = Account.objects.create(name="MoMo", opening_date=date(2026, 1, 1))
        today = timezone.localdate()
        cls.sub = subscriptions.create_subscription.sync(
            cls.admin, client=cls.school, project=cls.product, title="Standard plan", lines=PLAN,
            start_date=today - timedelta(days=40), interval_months=1, external_ref="olympus", auto_issue=True)
        subscriptions.bill_due_subscriptions(today)  # two periods: the older one overdue, the current one due later
        cls.invoices = list(Invoice.objects.filter(subscription=cls.sub).order_by("period_start"))
        Invoice.objects.filter(pk=cls.invoices[0].pk).update(due_date=today - timedelta(days=5))
        cls.foreign = subscriptions.create_subscription.sync(
            cls.admin, client=cls.garage, project=cls.other, title="Garage plan", lines=PLAN, start_date=today,
            interval_months=1, external_ref="mechbrif")
        cls.key, cls.raw = create_api_key.sync(cls.admin, name="School SaaS server", product=cls.product)
        cls.draft = invoices.create_invoice.sync(cls.admin, client=cls.school, project=cls.product, lines=PLAN)

    def setUp(self):
        cache.clear()

    def get(self, path, key=None):
        return self.client.get(f"/api/v1{path}", headers={"Authorization": f"Bearer {key or self.raw}"})

    def test_health_needs_no_key(self):
        self.assertEqual(self.client.get("/api/v1/health").json()["status"], "ok")

    def test_bad_or_missing_key(self):
        self.assertEqual(self.client.get("/api/v1/product").status_code, 401)
        self.assertEqual(self.get("/product", key="dak_00000000_nope").status_code, 401)
        self.assertEqual(self.get("/product", key=self.raw[:-1] + "x").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/product", headers={"Authorization": f"Token {self.raw}"}).status_code, 401)

    def test_revoked_key_is_cut_off(self):
        key, raw = create_api_key.sync(self.admin, name="temp", product=self.product)
        self.assertEqual(self.get("/product", key=raw).status_code, 200)
        revoke_api_key.sync(key, self.admin)
        self.assertEqual(self.get("/product", key=raw).status_code, 401)

    def test_product(self):
        data = self.get("/product").json()
        self.assertEqual((data["code"], data["active_subscriptions"]), ("school-saas", 1))
        self.assertEqual(Decimal(data["monthly_value"]), Decimal(150000))

    def test_subscriptions_are_scoped_to_the_keys_product(self):
        data = self.get("/subscriptions").json()
        self.assertEqual(data["count"], 1)
        sub = data["items"][0]
        self.assertEqual((sub["external_ref"], sub["client"]["name"]), ("olympus", "Olympus Pre-school"))
        self.assertFalse(sub["paid_up"])  # the older invoice is overdue
        self.assertEqual(Decimal(sub["owing"]), Decimal(300000))
        self.assertEqual(self.get(f"/subscriptions/{self.foreign.pk}").status_code, 404)

    def test_customer_status_follows_payments(self):
        status = self.get("/customers/olympus/status").json()
        self.assertTrue(status["has_active_subscription"])
        self.assertFalse(status["paid_up"])
        self.assertIsNone(status["paid_through"])
        for invoice in self.invoices:
            receipts.record_payment.sync(invoice, self.admin, amount=invoice.total, date=timezone.localdate(),
                                         account=self.momo)
        status = self.get("/customers/olympus/status").json()
        self.assertTrue(status["paid_up"])
        self.assertEqual(status["paid_through"], self.invoices[-1].period_end.isoformat())
        self.assertEqual(Decimal(status["owing"]), 0)
        unknown = self.get("/customers/nobody/status").json()
        self.assertEqual((unknown["has_active_subscription"], unknown["subscriptions"]), (False, []))
        self.assertEqual(self.get("/customers/mechbrif/status").json()["subscriptions"], [])  # other product's

    def test_invoices_hide_drafts_and_other_products(self):
        data = self.get("/invoices").json()
        ids = {i["id"] for i in data["items"]}
        self.assertEqual(ids, {i.pk for i in self.invoices})
        self.assertNotIn(self.draft.pk, ids)
        detail = self.get(f"/invoices/{self.invoices[0].pk}").json()
        self.assertEqual(detail["lines"][0]["description"], "Standard plan")
        self.assertEqual(self.get(f"/invoices/{self.draft.pk}").status_code, 404)

    def test_pdfs_and_receipts(self):
        invoice = self.invoices[0]
        receipt = receipts.record_payment.sync(invoice, self.admin, amount=50000, date=timezone.localdate(), account=self.momo)
        pdf = self.get(f"/invoices/{invoice.pk}/pdf")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        listed = self.get("/receipts").json()["items"]
        self.assertEqual([r["number"] for r in listed], [receipt.number])
        self.assertTrue(self.get(listed[0]["pdf_url"].removeprefix("/api/v1")).content.startswith(b"%PDF"))

    def test_updated_since_and_pagination(self):
        future = (timezone.now() + timedelta(hours=1)).isoformat()
        self.assertEqual(self.client.get("/api/v1/subscriptions", {"updated_since": future},
                                         headers={"Authorization": f"Bearer {self.raw}"}).json()["count"], 0)
        page = self.client.get("/api/v1/invoices", {"limit": 1}, headers={"Authorization": f"Bearer {self.raw}"}).json()
        self.assertEqual((page["count"], len(page["items"])), (2, 1))

    def test_rate_limit(self):
        from apps.api.api import api
        throttle = api.throttle[0] if isinstance(api.throttle, list) else api.throttle
        old = throttle.rate, throttle.num_requests, throttle.duration
        throttle.rate, (throttle.num_requests, throttle.duration) = "2/m", throttle.parse_rate("2/m")
        try:
            codes = [self.get("/product").status_code for _ in range(3)]
        finally:
            throttle.rate, throttle.num_requests, throttle.duration = old
        self.assertEqual(codes, [200, 200, 429])

    def test_docs_admins_only(self):
        self.assertEqual(self.client.get("/api/v1/docs").status_code, 302)  # to sign in
        staff = get_user_model().objects.create_user("staff@dakdot.com", password="x" * 12)
        StaffProfile.objects.create(user=staff, role=StaffProfile.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/api/v1/docs").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/api/v1/docs").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/openapi.json").status_code, 200)

    def test_key_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/app/settings/api-keys/").status_code, 200)
        self.assertEqual(self.client.get("/app/settings/api-keys/new/").status_code, 200)
        response = self.client.post("/app/settings/api-keys/new/", {"name": "Second server", "product": self.product.pk},
                                    headers={"HX-Request": "true"})
        self.assertContains(response, "dak_")
        self.assertEqual(self.client.post(f"/app/settings/api-keys/{self.key.pk}/revoke/", headers={"HX-Request": "true"}).status_code, 204)

    def test_keys_only_for_products(self):
        from django.core.exceptions import ValidationError
        internal = Project.objects.create(title="Website", kind=Project.Kind.INTERNAL)
        with self.assertRaises(ValidationError):
            create_api_key.sync(self.admin, name="x", product=internal)
