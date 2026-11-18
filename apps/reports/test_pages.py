"""Every page renders for a signed-in admin, with real templates and a little data: catches template errors."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.services import invoices, quotations, receipts
from apps.clients.models import Client
from apps.core.models import StaffProfile
from apps.finance import services as finance
from apps.finance.models import Account, ExpenseCategory
from apps.projects.models import Project

LINES = [{"description": "Pull-up Banners", "quantity": "2", "unit_price": "245000"},
         {"description": "Binding", "unit_price": "50000", "is_lump_sum": True}]


class PageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user("admin@dakdot.com", password="x" * 12, first_name="Elijah")
        StaffProfile.objects.create(user=cls.admin, role=StaffProfile.Role.ADMIN)
        cls.momo = Account.objects.create(name="MTN Mobile Money", account_number="+256 760 971269",
                                          account_name="ELIJAH ANGENGEUN", opening_date=date(2026, 1, 1))
        cls.bank = Account.objects.create(name="Stanbic Bank", account_number="9030020754582", swift_code="SBICUGKXXXX",
                                          account_name="DAKDOT CREATIONS LIMITED", opening_date=date(2026, 1, 1))
        cls.client_ = Client.objects.create(name="Olympus Pre-school", contact_person="Head teacher")
        cls.project = Project.objects.create(client=cls.client_, title="End of year 2026")
        today = timezone.localdate()
        cls.own_project = Project.objects.create(title="Dakdot website", kind=Project.Kind.INTERNAL)
        cls.product = Project.objects.create(title="School SaaS", kind=Project.Kind.PRODUCT, code="school-saas")
        from apps.billing.services import subscriptions
        cls.subscription = subscriptions.create_subscription.sync(
            cls.admin, client=cls.client_, project=cls.product, title="Standard plan", start_date=today,
            interval_months=1, lines=[{"description": "Standard plan", "unit_price": "150000"}])
        subscriptions.invoice_now.sync(cls.subscription, cls.admin)
        today = timezone.localdate()
        q = quotations.create_quotation.sync(cls.admin, client=cls.client_, project=cls.project, lines=LINES)
        cls.quotation = quotations.issue_quotation.sync(q, cls.admin)
        cls.invoice = invoices.issue_invoice.sync(quotations.convert_to_invoice.sync(cls.quotation, cls.admin), cls.admin)
        cls.draft = invoices.create_invoice.sync(cls.admin, client=cls.client_, lines=LINES, notes="Draft notes")
        cls.receipt = receipts.record_payment.sync(cls.invoice, cls.admin, amount=300000, date=today, account=cls.momo,
                                                   reference="45043495373")
        cls.deposit = receipts.record_deposit.sync(cls.client_, cls.admin, amount=200000, date=today, account=cls.bank)
        from apps.finance import loans
        cls.loan = loans.record_loan.sync(cls.admin, amount=500000, date=today, account=cls.bank, purpose="Start-up",
                                          lender_name="Centenary SACCO")
        loans.repay_loan.sync(cls.loan, cls.admin, amount=100000, date=today, account=cls.bank)
        category = ExpenseCategory.objects.create(name="Printing")
        cls.expense = finance.record_expense.sync(cls.admin, date=today, amount=120000, account=cls.momo,
                                                  category=category, description="Banner printing", project=cls.project)
        finance.record_transfer.sync(cls.admin, date=today, from_account=cls.momo, to_account=cls.bank, amount=100000, fee=1500)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_pages_render(self):
        pages = [
            reverse("reports:dashboard"), reverse("reports:search") + "?q=oly",
            reverse("clients:list"), reverse("clients:list") + "?q=oly", reverse("clients:detail", args=[self.client_.pk]),
            reverse("clients:new"), reverse("clients:edit", args=[self.client_.pk]),
            reverse("clients:statement", args=[self.client_.pk]),
            reverse("projects:list"), reverse("projects:list") + "?status=all", reverse("projects:detail", args=[self.project.pk]),
            reverse("projects:detail", args=[self.own_project.pk]), reverse("projects:edit", args=[self.own_project.pk]),
            reverse("projects:products"), reverse("projects:detail", args=[self.product.pk]),
            reverse("projects:new") + "?kind=product", reverse("projects:new") + "?kind=internal",
            reverse("billing:subscriptions"), reverse("billing:subscriptions") + "?status=all",
            reverse("billing:subscription", args=[self.subscription.pk]), reverse("billing:subscription-new"),
            reverse("billing:subscription-edit", args=[self.subscription.pk]),
            reverse("finance:income-new") + f"?project={self.product.pk}",
            reverse("projects:new"), reverse("projects:edit", args=[self.project.pk]),
            reverse("billing:quotations"), reverse("billing:quotation", args=[self.quotation.pk]),
            reverse("billing:quotation-new") + f"?project={self.project.pk}",
            reverse("billing:invoices"), reverse("billing:invoices") + "?status=overdue",
            reverse("billing:invoice", args=[self.invoice.pk]), reverse("billing:invoice", args=[self.draft.pk]),
            reverse("billing:invoice-new"), reverse("billing:invoice-edit", args=[self.draft.pk]),
            reverse("billing:receipts"), reverse("billing:receipt", args=[self.receipt.pk]),
            reverse("billing:receipt", args=[self.deposit.pk]),
            reverse("finance:accounts"), reverse("finance:account", args=[self.momo.pk]),
            reverse("finance:account-new"), reverse("finance:account-edit", args=[self.momo.pk]),
            reverse("finance:transactions"), reverse("finance:expenses"), reverse("finance:expense", args=[self.expense.pk]),
            reverse("finance:expense-new"), reverse("finance:transfer-new"), reverse("finance:income-new"),
            reverse("finance:adjustment-new"), reverse("finance:loans"), reverse("finance:loans") + "?status=all",
            reverse("finance:loan-new"), reverse("finance:loan", args=[self.loan.pk]),
            reverse("core:company"), reverse("core:staff"), reverse("core:staff-new"),
        ]
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_partials_for_live_search(self):
        response = self.client.get(reverse("billing:invoices") + "?q=INV", headers={"HX-Request": "true", "HX-Target": "invoice-rows"})
        self.assertContains(response, 'id="invoice-rows"')
        self.assertNotContains(response, "<html")

    def test_pdfs(self):
        for kind, pk in (("invoice", self.invoice.pk), ("quotation", self.quotation.pk), ("receipt", self.receipt.pk), ("receipt", self.deposit.pk),
                         ("statement", self.client_.pk)):
            with self.subTest(kind=kind):
                response = self.client.get(reverse("documents:pdf", args=[kind, pk]))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b"%PDF"))
                self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(f'filename="{self.invoice.number}.pdf"',
                      self.client.get(reverse("documents:pdf", args=["invoice", self.invoice.pk]))["Content-Disposition"])
        self.assertEqual(self.client.get(reverse("documents:pdf", args=["invoice", self.draft.pk])).status_code, 404)

    def test_save_draft_from_the_editor(self):
        response = self.client.post(reverse("billing:invoice-new"), {
            "client": self.client_.pk, "project": "", "date_limit": "", "notes": "", "terms": "One\nTwo",
            "description": ["Bags", "Binding"], "note": ["", ""], "quantity": ["18", "1"],
            "unit_price": ["40,000", "50,000"], "lump_sum": ["0", "1"],
        }, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)
        from apps.billing.models import Invoice
        invoice = Invoice.objects.latest("created_at")
        self.assertEqual(invoice.total, 770000)

    def test_record_payment_from_the_dialog(self):
        response = self.client.post(reverse("billing:invoice-pay", args=[self.invoice.pk]), {
            "amount": "100,000", "date": timezone.localdate().isoformat(), "account": self.bank.pk, "reference": "",
            "being_payment_for": "Second instalment"}, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)

    def test_deposit_and_apply_from_the_dialogs(self):
        response = self.client.post(reverse("billing:deposit-new", args=[self.client_.pk]), {
            "amount": "50,000", "date": timezone.localdate().isoformat(), "account": self.bank.pk, "fee": "0",
            "reference": "", "quotation": self.quotation.pk, "project": "", "being_payment_for": ""},
            headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)
        response = self.client.post(reverse("billing:invoice-apply-credit", args=[self.invoice.pk]), {"amount": "10,000"},
                                    headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)
        response = self.client.post(reverse("billing:receipt-apply", args=[self.deposit.pk]),
                                    {"invoice": self.invoice.pk, "amount": ""}, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)
        self.assertContains(self.client.get(reverse("billing:invoice", args=[self.invoice.pk])), "Credit applied")

    def test_errors_come_back_as_422(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = self.client.post(reverse("billing:invoice-pay", args=[self.invoice.pk]), {
            "amount": "1,000", "date": tomorrow.isoformat(), "account": self.bank.pk},
            headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "cannot be in the future", status_code=422)

    def test_staff_cannot_open_money_pages(self):
        user = get_user_model().objects.create_user("staff@dakdot.com", password="x" * 12)
        StaffProfile.objects.create(user=user, role=StaffProfile.Role.STAFF)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("finance:accounts")).status_code, 403)
        self.assertEqual(self.client.get(reverse("billing:invoices")).status_code, 200)


class SubscriptionPageTests(PageTests):
    def test_subscription_form_and_actions(self):
        from apps.billing.models import Subscription
        response = self.client.post(reverse("billing:subscription-new"), {
            "client": self.client_.pk, "project": self.product.pk, "title": "Premium plan", "interval_months": "12",
            "start_date": "2026-12-01", "end_date": "", "due_days": "7", "external_ref": "olympus", "notes": "",
            "description": ["Premium plan"], "note": [""], "quantity": ["1"], "unit_price": ["1,500,000"], "lump_sum": ["0"],
        }, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)
        sub = Subscription.objects.get(title="Premium plan")
        self.assertEqual(sub.amount, 1500000)
        self.assertEqual(sub.monthly_value, 125000)
        for name in ("billing:subscription-pause", "billing:subscription-resume", "billing:subscription-invoice-now"):
            self.assertEqual(self.client.post(reverse(name, args=[sub.pk]), headers={"HX-Request": "true"}).status_code, 204, name)

    def test_project_form_kinds(self):
        response = self.client.post(reverse("projects:new"), {"kind": "product", "title": "Gearhouse", "code": "gearhouse",
                                                              "client": "", "status": "active"}, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 204, response.content)
        response = self.client.post(reverse("projects:new"), {"kind": "client", "title": "No client", "code": "",
                                                              "client": "", "status": "active"}, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 422)
