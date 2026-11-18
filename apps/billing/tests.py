from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Invoice, Quotation, Receipt
from apps.billing.services import invoices, quotations, receipts
from apps.clients.models import Client
from apps.core.mixins.numbering import format_number
from apps.core.models import StaffProfile
from apps.finance import selectors as finance_selectors
from apps.finance.models import Account, Transaction

OLYMPUS_LINES = [
    {"description": "Junior Kindergarten report", "note": "A3-A4", "quantity": "18", "unit_price": "5000"},
    {"description": "Senior Kindergarten report", "note": "A3-A4", "quantity": "17", "unit_price": "5000"},
    {"description": "Grade 1 - Grade 4 report", "note": "A4-A5", "quantity": "17", "unit_price": "3800"},
    {"description": "Reception", "quantity": "26", "unit_price": "5000"},
    {"description": "Tulips", "quantity": "31", "unit_price": "5000"},
    {"description": "Special Needs", "quantity": "2", "unit_price": "5000"},
    {"description": "Binding", "unit_price": "50000", "is_lump_sum": True},
    {"description": "Bags", "quantity": "18", "unit_price": "40000"},
    {"description": "Pull-up Banners", "quantity": "2", "unit_price": "245000"},
    {"description": "Certificates for graduands", "quantity": "17", "unit_price": "5000"},
]


def make_user(role, email):
    user = get_user_model().objects.create_user(email, password="x" * 12, first_name=role.title())
    StaffProfile.objects.create(user=user, role=role)
    return user


class BillingFlowTests(TestCase):
    def setUp(self):
        self.finance = make_user(StaffProfile.Role.FINANCE, "finance@dakdot.com")
        self.staff = make_user(StaffProfile.Role.STAFF, "staff@dakdot.com")
        self.client_ = Client.objects.create(name="Olympus Pre-school")
        self.momo = Account.objects.create(name="MTN Mobile Money", kind=Account.Kind.MOBILE_MONEY,
                                           opening_date=date(2026, 1, 1))
        self.today = timezone.localdate()

    def issued_invoice(self):
        invoice = invoices.create_invoice.sync(self.staff, client=self.client_, lines=OLYMPUS_LINES)
        return invoices.issue_invoice.sync(invoice, self.finance)

    def test_olympus_invoice_total(self):
        # The hand-made INV261000111 says 1,869,400, but two of its rows don't multiply out: Grade 1-4 is
        # 3,800 x 17 = 64,600 (printed 49,400) and Tulips is 5,000 x 31 = 155,000 (printed 160,000).
        invoice = invoices.create_invoice.sync(self.staff, client=self.client_, lines=OLYMPUS_LINES)
        self.assertEqual(invoice.total, Decimal("1879600"))
        self.assertEqual(invoice.number, "")  # drafts have no number
        binding = invoice.lines.get(description="Binding")
        self.assertTrue(binding.is_lump_sum)
        self.assertEqual(binding.quantity, 1)

    def test_issue_numbers_from_today_and_counts_per_day(self):
        first = self.issued_invoice()
        second = self.issued_invoice()
        self.assertEqual(first.number, format_number("INV", self.today, 500))
        self.assertEqual(second.number, format_number("INV", self.today, 501))
        self.assertEqual(first.date, self.today)

    def test_number_format(self):
        self.assertEqual(format_number("INV", date(2026, 11, 10), 1), "INV261000111")
        self.assertEqual(format_number("RCT", date(2026, 11, 13), 1), "RCT261300111")
        self.assertEqual(format_number("INV", date(2026, 11, 18), 500), "INV261850011")

    def test_staff_cannot_issue_invoices(self):
        invoice = invoices.create_invoice.sync(self.staff, client=self.client_, lines=OLYMPUS_LINES)
        with self.assertRaises(ValidationError):
            invoices.issue_invoice.sync(invoice, self.staff)

    def test_issued_invoice_is_frozen(self):
        invoice = self.issued_invoice()
        with self.assertRaises(ValidationError):
            invoices.update_invoice.sync(invoice, self.staff, client=self.client_, lines=OLYMPUS_LINES[:1])

    def test_down_payment_then_balance(self):
        invoice = self.issued_invoice()
        receipt = receipts.record_payment.sync(invoice, self.finance, amount=Decimal(800000), date=self.today,
                                               account=self.momo, reference="45043495373")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)
        self.assertEqual(invoice.balance, Decimal(1079600))
        self.assertEqual(receipt.number, format_number("RCT", self.today, 500))
        self.assertEqual(receipt.previously_paid, 0)
        self.assertEqual(receipt.balance_due, Decimal(1079600))
        self.assertEqual(receipt.amount_in_words, "Eight hundred thousand shillings only")
        self.assertEqual(receipt.transactions.get().account, self.momo)

        second = receipts.record_payment.sync(invoice, self.finance, amount=Decimal(1079600), date=self.today,
                                              account=self.momo)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(second.previously_paid, Decimal(800000))
        self.assertEqual(second.balance_due, 0)

    def test_receipt_number_uses_the_payment_date(self):
        invoice = invoices.create_invoice.sync(self.staff, client=self.client_, lines=OLYMPUS_LINES)
        invoice = invoices.issue_invoice.sync(invoice, self.finance)
        Invoice.objects.filter(pk=invoice.pk).update(date=self.today - timedelta(days=5))
        invoice.refresh_from_db()
        paid_on = self.today - timedelta(days=3)
        receipt = receipts.record_payment.sync(invoice, self.finance, amount=100, date=paid_on, account=self.momo)
        self.assertEqual(receipt.number, format_number("RCT", paid_on, 500))

    def test_overpayment_is_kept_as_credit(self):
        invoice = self.issued_invoice()  # 1,879,600
        receipt = receipts.record_payment.sync(invoice, self.finance, amount=Decimal(2000000), date=self.today, account=self.momo)
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.amount_paid), (Invoice.Status.PAID, Decimal(1879600)))
        self.assertEqual(receipts.unapplied(receipt), Decimal(120400))
        self.assertEqual(receipt.kept_as_credit, Decimal(120400))
        self.assertEqual(receipt.balance_due, 0)

    def test_cannot_pay_a_draft(self):
        draft = invoices.create_invoice.sync(self.staff, client=self.client_, lines=OLYMPUS_LINES)
        with self.assertRaises(ValidationError):
            receipts.record_payment.sync(draft, self.finance, amount=100, date=self.today, account=self.momo)

    def test_void_receipt_puts_the_balance_back(self):
        invoice = self.issued_invoice()
        receipt = receipts.record_payment.sync(invoice, self.finance, amount=800000, date=self.today, account=self.momo)
        receipts.void_receipt.sync(receipt, self.finance, reason="Entered twice")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertEqual(invoice.amount_paid, 0)
        self.assertTrue(receipt.transactions.get().is_void)
        self.assertEqual(Receipt.objects.get(pk=receipt.pk).status, Receipt.Status.VOID)

    def test_voiding_an_invoice_returns_its_payments_as_credit(self):
        invoice = self.issued_invoice()
        receipt = receipts.record_payment.sync(invoice, self.finance, amount=100, date=self.today, account=self.momo)
        invoices.void_invoice.sync(invoice, self.finance, reason="Wrong prices")
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.amount_paid), (Invoice.Status.VOID, 0))
        self.assertEqual(receipts.unapplied(receipt), 100)  # the money is still the client's

    def test_account_balance_follows_receipts(self):
        Account.objects.filter(pk=self.momo.pk).update(opening_balance=50000)
        invoice = self.issued_invoice()
        receipts.record_payment.sync(invoice, self.finance, amount=800000, date=self.today, account=self.momo)
        balance = {a.pk: a.balance for a in async_to_list(finance_selectors.balances())}
        self.assertEqual(balance[self.momo.pk], Decimal(850000))

    def test_quotation_to_invoice(self):
        quotation = quotations.create_quotation.sync(self.staff, client=self.client_, lines=OLYMPUS_LINES)
        quotation = quotations.issue_quotation.sync(quotation, self.staff)
        self.assertTrue(quotation.number.startswith("QUO"))
        self.assertIsNotNone(quotation.valid_until)
        invoice = quotations.convert_to_invoice.sync(quotation, self.staff)
        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.Status.ACCEPTED)
        self.assertEqual(invoice.total, quotation.total)
        self.assertEqual(invoice.lines.count(), len(OLYMPUS_LINES))
        self.assertTrue(invoice.is_draft)
        with self.assertRaises(ValidationError):
            quotations.convert_to_invoice.sync(quotation, self.staff)


class CreditTests(TestCase):
    """Deposits: money before the invoice, kept as the client's credit and applied later."""

    def setUp(self):
        self.finance = make_user(StaffProfile.Role.FINANCE, "finance@dakdot.com")
        self.client_ = Client.objects.create(name="Olympus Pre-school")
        self.momo = Account.objects.create(name="MTN Mobile Money", opening_date=date(2026, 1, 1))
        self.today = timezone.localdate()
        quotation = quotations.create_quotation.sync(self.finance, client=self.client_, lines=OLYMPUS_LINES)
        self.quotation = quotations.issue_quotation.sync(quotation, self.finance)

    def deposit(self, amount, **links):
        return receipts.record_deposit.sync(self.client_, self.finance, amount=Decimal(amount), date=self.today,
                                            account=self.momo, **links)

    def invoice(self, lines=OLYMPUS_LINES):
        draft = invoices.create_invoice.sync(self.finance, client=self.client_, lines=lines)
        return invoices.issue_invoice.sync(draft, self.finance)

    def test_deposit_on_a_quotation_pays_its_invoice_when_issued(self):
        deposit = self.deposit(1000000, quotation=self.quotation)
        self.assertIsNone(deposit.invoice_id)
        self.assertEqual(deposit.being_payment_for, f"Deposit on quotation {self.quotation.number}.")
        self.assertEqual(deposit.transactions.get().amount, 1000000)  # in the account the day it came

        draft = quotations.convert_to_invoice.sync(self.quotation, self.finance)
        invoice = invoices.issue_invoice.sync(draft, self.finance)
        self.assertEqual((invoice.status, invoice.amount_paid, invoice.balance),
                         (Invoice.Status.PARTIAL, Decimal(1000000), Decimal(879600)))
        self.assertEqual(receipts.unapplied(deposit), 0)
        self.assertEqual(Transaction.objects.filter(kind=Transaction.Kind.RECEIPT).count(), 1)  # no money moved twice

    def test_unlinked_credit_waits_to_be_applied_by_hand(self):
        deposit = self.deposit(500000)
        invoice = self.invoice()
        self.assertEqual(invoice.amount_paid, 0)
        applied = receipts.apply_credit.sync(invoice, self.finance)
        invoice.refresh_from_db()
        self.assertEqual((applied, invoice.amount_paid), (Decimal(500000), Decimal(500000)))
        self.assertEqual(receipts.unapplied(deposit), 0)
        with self.assertRaises(ValidationError):
            receipts.apply_credit.sync(invoice, self.finance)  # nothing left

    def test_one_deposit_pays_two_invoices_and_credit_can_be_taken_back(self):
        deposit = self.deposit(2000000)
        first = self.invoice()  # 1,879,600
        second = self.invoice([{"description": "Hosting", "unit_price": "300000", "is_lump_sum": True}])
        receipts.apply_credit.sync(first, self.finance, receipt=deposit)
        receipts.apply_credit.sync(second, self.finance, receipt=deposit)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.status, second.amount_paid), (Invoice.Status.PAID, Decimal(120400)))
        self.assertEqual(receipts.unapplied(deposit), 0)

        receipts.remove_allocation.sync(second.allocations.get(), self.finance)
        second.refresh_from_db()
        self.assertEqual((second.status, second.amount_paid), (Invoice.Status.ISSUED, 0))
        self.assertEqual(receipts.unapplied(deposit), Decimal(120400))

    def test_apply_checks_amounts(self):
        self.deposit(100000)
        invoice = self.invoice()
        with self.assertRaises(ValidationError):
            receipts.apply_credit.sync(invoice, self.finance, amount=200000)  # more than the credit
        receipts.apply_credit.sync(invoice, self.finance, amount=40000)
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 40000)

    def test_voiding_a_deposit_makes_its_invoice_owe_again(self):
        deposit = self.deposit(1000000, quotation=self.quotation)
        invoice = invoices.issue_invoice.sync(quotations.convert_to_invoice.sync(self.quotation, self.finance), self.finance)
        receipts.void_receipt.sync(deposit, self.finance, reason="Bounced")
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.amount_paid), (Invoice.Status.ISSUED, 0))

    def test_deposit_must_be_for_the_clients_own_quotation(self):
        other = Client.objects.create(name="Another school")
        with self.assertRaises(ValidationError):
            receipts.record_deposit.sync(other, self.finance, amount=100, date=self.today, account=self.momo,
                                         quotation=self.quotation)

    def test_statement_shows_credit(self):
        from apps.clients.selectors import statement
        self.deposit(300000)
        rows, balance = async_to_list(statement(self.client_))
        self.assertEqual(balance, Decimal(-300000))
        self.assertEqual(rows[0]["what"], "Payment on account")


def async_to_list(coro):
    from asgiref.sync import async_to_sync

    async def run():
        return await coro
    return async_to_sync(run)()


class FinanceTests(TestCase):
    def setUp(self):
        from apps.finance.models import ExpenseCategory
        self.finance = make_user(StaffProfile.Role.FINANCE, "finance@dakdot.com")
        self.momo = Account.objects.create(name="MoMo", opening_balance=500000, opening_date=date(2026, 1, 1))
        self.bank = Account.objects.create(name="Bank", opening_balance=0, opening_date=date(2026, 1, 1))
        self.category = ExpenseCategory.objects.create(name="Printing")
        self.today = timezone.localdate()

    def balances(self):
        return {a.name: a.balance for a in async_to_list(finance_selectors.balances())}

    def test_expense_and_transfer(self):
        from apps.finance import services
        services.record_expense.sync(self.finance, date=self.today, amount=100000, account=self.momo,
                                     category=self.category, description="Bags")
        services.record_transfer.sync(self.finance, date=self.today, from_account=self.momo, to_account=self.bank,
                                      amount=300000, fee=2500)
        self.assertEqual(self.balances(), {"MoMo": Decimal(97500), "Bank": Decimal(300000)})
        totals = async_to_list(finance_selectors.month_totals(self.today.year, self.today.month))
        self.assertEqual(totals["out"], Decimal(102500))  # expense + fee; the transfer itself is not spending

    def test_void_expense_returns_money(self):
        from apps.finance import services
        expense = services.record_expense.sync(self.finance, date=self.today, amount=100000, account=self.momo,
                                               category=self.category, description="Bags")
        services.void_expense.sync(expense, self.finance, reason="Duplicate")
        self.assertEqual(self.balances()["MoMo"], Decimal(500000))
        self.assertTrue(Transaction.objects.get(expense=expense).is_void)


class FeeTests(TestCase):
    """A fee is always its own FEE line on the same account, linked to what it was charged on."""

    def setUp(self):
        from apps.finance.models import ExpenseCategory
        self.finance = make_user(StaffProfile.Role.FINANCE, "finance@dakdot.com")
        self.momo = Account.objects.create(name="MoMo", opening_balance=500000, opening_date=date(2026, 1, 1))
        self.category = ExpenseCategory.objects.create(name="Printing")
        self.client_ = Client.objects.create(name="Olympus Pre-school")
        self.today = timezone.localdate()

    def balance(self):
        return {a.name: a.balance for a in async_to_list(finance_selectors.balances())}["MoMo"]

    def test_expense_fee_is_a_second_line(self):
        from apps.finance import services
        expense = services.record_expense.sync(self.finance, date=self.today, amount=450000, fee=3500,
                                               account=self.momo, category=self.category, description="Bags",
                                               payee="Kampala Printers")
        lines = list(expense.transactions.order_by("id"))
        self.assertEqual([(t.kind, t.amount) for t in lines],
                         [(Transaction.Kind.EXPENSE, Decimal(450000)), (Transaction.Kind.FEE, Decimal(3500))])
        self.assertEqual(lines[1].description, "Fee on: Bags (Kampala Printers)")
        self.assertEqual(self.balance(), Decimal(46500))
        services.void_expense.sync(expense, self.finance, reason="Wrong account")
        self.assertEqual(self.balance(), Decimal(500000))  # both lines voided

    def test_payment_fee_credits_the_client_in_full(self):
        invoice = invoices.issue_invoice.sync(
            invoices.create_invoice.sync(self.finance, client=self.client_, lines=OLYMPUS_LINES[:1]), self.finance)
        receipt = receipts.record_payment.sync(invoice, self.finance, amount=90000, fee=1000, date=self.today,
                                               account=self.momo)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)  # the client paid 90,000
        self.assertEqual(receipt.net_received, Decimal(89000))
        self.assertEqual(self.balance(), Decimal(589000))  # 500,000 + 90,000 - 1,000
        self.assertEqual(receipt.transactions.filter(kind=Transaction.Kind.FEE).get().amount, Decimal(1000))
        receipts.void_receipt.sync(receipt, self.finance, reason="Test")
        self.assertEqual(self.balance(), Decimal(500000))

    def test_fee_cannot_swallow_the_amount(self):
        from apps.finance import services
        with self.assertRaises(ValidationError):
            services.record_expense.sync(self.finance, date=self.today, amount=1000, fee=-5, account=self.momo,
                                         category=self.category, description="x")
        invoice = invoices.issue_invoice.sync(
            invoices.create_invoice.sync(self.finance, client=self.client_, lines=OLYMPUS_LINES[:1]), self.finance)
        with self.assertRaises(ValidationError):
            receipts.record_payment.sync(invoice, self.finance, amount=1000, fee=1000, date=self.today, account=self.momo)


class OwnProjectTests(TestCase):
    """Projects without a client: Dakdot's internal work and its own products."""

    def setUp(self):
        from apps.projects.models import Project
        self.finance = make_user(StaffProfile.Role.FINANCE, "finance@dakdot.com")
        self.product = Project.objects.create(title="School SaaS", kind=Project.Kind.PRODUCT, code="school-saas")
        self.school_a = Client.objects.create(name="School A")
        self.school_b = Client.objects.create(name="School B")
        self.client_project = Project.objects.create(title="Reports", client=self.school_a)

    def test_own_project_takes_invoices_for_any_client(self):
        for school in (self.school_a, self.school_b):
            invoice = invoices.create_invoice.sync(self.finance, client=school, project=self.product, lines=OLYMPUS_LINES[:1])
            self.assertEqual(invoice.project, self.product)
        self.assertEqual(str(self.product), "School SaaS (Our product)")

    def test_client_project_only_takes_its_client(self):
        with self.assertRaises(ValidationError):
            invoices.create_invoice.sync(self.finance, client=self.school_b, project=self.client_project, lines=OLYMPUS_LINES[:1])


class ProjectKindTests(TestCase):
    def test_kind_rules(self):
        from apps.projects.models import Project
        client = Client.objects.create(name="Olympus")
        with self.assertRaises(ValidationError):
            Project(title="Reports", kind=Project.Kind.CLIENT).full_clean(exclude=["created_by"])  # client work needs a client
        with self.assertRaises(ValidationError):
            Project(title="Site", kind=Project.Kind.INTERNAL, client=client).full_clean(exclude=["created_by"])  # internal has none
        with self.assertRaises(ValidationError):
            Project(title="SaaS", kind=Project.Kind.PRODUCT).full_clean(exclude=["created_by"])  # products need a code
        Project(title="SaaS", kind=Project.Kind.PRODUCT, code="saas").full_clean(exclude=["created_by"])

    def test_product_income_includes_other_income(self):
        from apps.finance import services
        from apps.projects import selectors
        from apps.projects.models import Project
        finance = make_user(StaffProfile.Role.FINANCE, "f@dakdot.com")
        momo = Account.objects.create(name="MoMo", opening_date=date(2026, 1, 1))
        product = Project.objects.create(title="SaaS", kind=Project.Kind.PRODUCT, code="saas")
        services.record_other_income.sync(finance, account=momo, amount=250000, date=timezone.localdate(),
                                          description="Play Store payout", project=product)
        money = async_to_list(selectors.money_summary(product))
        self.assertEqual(money["other_income"], Decimal(250000))
        self.assertEqual(money["income"], Decimal(250000))


class SubscriptionTests(TestCase):
    def setUp(self):
        from apps.projects.models import Project
        self.finance = make_user(StaffProfile.Role.FINANCE, "finance@dakdot.com")
        self.product = Project.objects.create(title="School SaaS", kind=Project.Kind.PRODUCT, code="school-saas")
        self.school = Client.objects.create(name="Olympus Pre-school")
        self.lines = [{"description": "Standard plan", "quantity": "1", "unit_price": "150000"}]

    def subscribe(self, start, **extra):
        from apps.billing.services import subscriptions
        return subscriptions.create_subscription.sync(
            self.finance, client=self.school, project=self.product, title="Standard plan", lines=self.lines,
            start_date=start, interval_months=1, external_ref="olympus", **extra)

    def test_bills_each_period_and_catches_up(self):
        from apps.billing.services.subscriptions import bill_due_subscriptions
        sub = self.subscribe(date(2026, 9, 1))
        made, errors = bill_due_subscriptions(date(2026, 11, 16))
        self.assertEqual(errors, [])
        self.assertEqual([(i.period_start, i.period_end) for i in made],
                         [(date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 10, 1), date(2026, 10, 31)),
                          (date(2026, 11, 1), date(2026, 11, 30))])
        self.assertTrue(all(i.is_draft and i.total == 150000 and i.project == self.product for i in made))
        sub.refresh_from_db()
        self.assertEqual(sub.next_invoice_date, date(2026, 12, 1))
        self.assertEqual(bill_due_subscriptions(date(2026, 11, 16)), ([], []))  # nothing twice

    def test_auto_issue_and_end_date(self):
        from apps.billing.services.subscriptions import bill_due_subscriptions
        sub = self.subscribe(date(2026, 10, 1), auto_issue=True, end_date=date(2026, 10, 31))
        made, _ = bill_due_subscriptions(date(2026, 11, 16))
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].status, Invoice.Status.ISSUED)
        self.assertTrue(made[0].number.startswith("INV"))
        sub.refresh_from_db()
        self.assertEqual(sub.status, sub.Status.ENDED)

    def test_paused_is_not_billed_and_resumes_from_today(self):
        from apps.billing.services import subscriptions
        sub = self.subscribe(date(2026, 9, 1))
        subscriptions.set_status.sync(sub, self.finance, status="paused")
        self.assertEqual(subscriptions.bill_due_subscriptions(date(2026, 11, 16)), ([], []))
        subscriptions.set_status.sync(sub, self.finance, status="active")
        sub.refresh_from_db()
        self.assertEqual(sub.next_invoice_date, timezone.localdate())

    def test_month_ends(self):
        from apps.core.dates import add_months, period_end
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(period_end(date(2026, 1, 15), 12), date(2027, 1, 14))
