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
        self.assertEqual(first.number, format_number("INV", self.today, 1))
        self.assertEqual(second.number, format_number("INV", self.today, 2))
        self.assertEqual(first.date, self.today)

    def test_number_format(self):
        self.assertEqual(format_number("INV", date(2026, 11, 10), 1), "INV261000111")
        self.assertEqual(format_number("RCT", date(2026, 11, 13), 1), "RCT261300111")

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
        self.assertEqual(receipt.number, format_number("RCT", self.today, 1))
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
        self.assertEqual(receipt.number, format_number("RCT", paid_on, 1))

    def test_cannot_overpay_or_pay_a_draft(self):
        invoice = self.issued_invoice()
        with self.assertRaises(ValidationError):
            receipts.record_payment.sync(invoice, self.finance, amount=Decimal(2000000), date=self.today, account=self.momo)
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

    def test_invoice_with_payments_cannot_be_voided(self):
        invoice = self.issued_invoice()
        receipts.record_payment.sync(invoice, self.finance, amount=100, date=self.today, account=self.momo)
        with self.assertRaises(ValidationError):
            invoices.void_invoice.sync(invoice, self.finance, reason="Wrong client")

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
