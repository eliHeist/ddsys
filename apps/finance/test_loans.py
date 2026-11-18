"""Money owed back: loans and top-ups from directors, staff or outsiders, and costs people paid themselves (all or
part), paid back in parts."""
from datetime import date
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.core.models import StaffProfile
from apps.finance import loans, selectors, services
from apps.finance.models import Account, ExpenseCategory, Loan, Transaction


def balances():
    return {a.name: a.balance for a in async_to_sync(selectors.balances)()}


class LoanTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("elijah@dakdot.com", password="x" * 12, first_name="Elijah",
                                                    last_name="Angengeun")
        self.director = StaffProfile.objects.create(user=user, role=StaffProfile.Role.ADMIN, is_director=True)
        self.by = user
        self.bank = Account.objects.create(name="Bank", opening_balance=0, opening_date=date(2026, 1, 1))
        self.category = ExpenseCategory.objects.create(name="Hosting")
        self.today = timezone.localdate()

    def loan(self, amount=1000000, **kw):
        return loans.record_loan.sync(self.by, amount=amount, date=self.today, account=self.bank,
                                      purpose="Laptop for the studio", **kw)

    def test_director_loan_lands_in_the_account_and_is_repaid_in_parts(self):
        loan = self.loan(person=self.director)
        self.assertEqual(loan.lender_name, "Elijah Angengeun")
        self.assertEqual(balances()["Bank"], 1000000)
        loans.repay_loan.sync(loan, self.by, amount=300000, date=self.today, account=self.bank, fee=1500)
        loans.repay_loan.sync(loan, self.by, amount=200000, date=self.today, account=self.bank)
        self.assertEqual(balances()["Bank"], 1000000 - 300000 - 1500 - 200000)
        self.assertEqual(loan.balance_with(loans.repaid(loan)), Decimal(500000))
        with self.assertRaises(ValidationError):
            loans.repay_loan.sync(loan, self.by, amount=600000, date=self.today, account=self.bank)  # more than owed
        totals = async_to_sync(selectors.loan_totals)()
        self.assertEqual((totals["directors"], totals["others"]), (Decimal(500000), 0))

    def test_outside_lender_by_name(self):
        loan = self.loan(lender_name="Centenary SACCO")
        self.assertIsNone(loan.person_id)
        self.assertEqual(async_to_sync(selectors.loan_totals)()["others"], Decimal(1000000))
        with self.assertRaises(ValidationError):
            self.loan()  # neither a director nor a name
        with self.assertRaises(ValidationError):
            self.loan(person=self.director, lender_name="Someone else")
        staff = StaffProfile.objects.create(
            user=get_user_model().objects.create_user("joel@dakdot.com", password="x" * 12, first_name="Joel"))
        self.assertEqual(self.loan(person=staff).lender_kind, "Staff")  # any staff member, not only directors

    def test_not_refundable_owes_nothing_and_cannot_be_repaid(self):
        loan = self.loan(person=self.director, must_repay=False)
        self.assertEqual(loan.balance_with(Decimal(0)), 0)
        with self.assertRaises(ValidationError):
            loans.repay_loan.sync(loan, self.by, amount=100, date=self.today, account=self.bank)
        loans.set_must_repay.sync(loan, self.by, must_repay=True)
        loans.repay_loan.sync(loan, self.by, amount=100, date=self.today, account=self.bank)

    def test_voiding(self):
        loan = self.loan(person=self.director)
        repayment = loans.repay_loan.sync(loan, self.by, amount=100000, date=self.today, account=self.bank)
        with self.assertRaises(ValidationError):
            loans.void_loan.sync(loan, self.by, reason="Typo")  # repayments first
        loans.void_repayment.sync(repayment, self.by, reason="Typo")
        loans.void_loan.sync(loan, self.by, reason="Typo")
        self.assertEqual(balances()["Bank"], 0)

    def test_director_pays_an_expense_from_their_own_pocket(self):
        expense = services.record_expense.sync(self.by, date=self.today, amount=250000, category=self.category,
                                               description="Server for a year", paid_by=self.director)
        self.assertIsNone(expense.account_id)
        self.assertEqual(expense.loan.lender_name, "Elijah Angengeun")
        self.assertEqual(expense.loan.amount, 250000)
        self.assertFalse(Transaction.objects.exists())  # no account moved
        self.assertEqual(balances()["Bank"], 0)
        # later the company pays the director back in two parts
        loans.repay_loan.sync(expense.loan, self.by, amount=150000, date=self.today, account=self.bank)
        with self.assertRaises(ValidationError):
            services.void_expense.sync(expense, self.by, reason="Wrong")  # part already repaid

    def test_voiding_a_director_paid_expense_voids_its_loan(self):
        expense = services.record_expense.sync(self.by, date=self.today, amount=50000, category=self.category,
                                               description="Domain", paid_by=self.director, must_repay=False)
        self.assertFalse(expense.loan.must_repay)
        services.void_expense.sync(expense, self.by, reason="Duplicate")
        self.assertEqual(Loan.objects.get(pk=expense.loan_id).status, Loan.Status.VOID)

    def test_staff_top_up_when_the_cash_ran_short(self):
        """Given money for transport, the job needed 150,000: 100,000 from the company's account, 50,000 their own."""
        user = get_user_model().objects.create_user("joel@dakdot.com", password="x" * 12, first_name="Joel")
        joel = StaffProfile.objects.create(user=user, role=StaffProfile.Role.STAFF)
        Account.objects.filter(pk=self.bank.pk).update(opening_balance=100000)
        expense = services.record_expense.sync(self.by, date=self.today, amount=150000, category=self.category,
                                               description="Transport to site", account=self.bank, paid_by=joel,
                                               paid_by_amount=50000, fee=500)
        self.assertEqual((expense.account_amount, expense.personal_amount), (Decimal(100000), Decimal(50000)))
        self.assertEqual(balances()["Bank"], 100000 - 100000 - 500)
        self.assertEqual(expense.loan.lender_kind, "Staff")
        self.assertTrue(expense.loan.paid_costs_directly)
        self.assertEqual(async_to_sync(selectors.loan_totals)()["staff"], Decimal(50000))
        loans.repay_loan.sync(expense.loan, self.by, amount=50000, date=self.today, account=self.bank)  # reimbursed
        self.assertEqual(async_to_sync(selectors.loan_totals)()["total"], 0)
        with self.assertRaises(ValidationError):
            services.record_expense.sync(self.by, date=self.today, amount=100, category=self.category, description="x",
                                         account=self.bank, paid_by=joel, paid_by_amount=100)  # all theirs: no account

    def test_staff_claim_for_the_whole_cost(self):
        user = get_user_model().objects.create_user("joel@dakdot.com", password="x" * 12, first_name="Joel")
        joel = StaffProfile.objects.create(user=user, role=StaffProfile.Role.STAFF)
        expense = services.record_expense.sync(self.by, date=self.today, amount=30000, category=self.category,
                                               description="Printer ink", paid_by=joel)
        self.assertEqual((expense.loan.amount, expense.loan.title), (30000, "Paid by Joel"))
        self.assertFalse(Transaction.objects.exists())

    def test_expense_needs_an_account_or_a_director(self):
        with self.assertRaises(ValidationError):
            services.record_expense.sync(self.by, date=self.today, amount=1, category=self.category, description="x")
        with self.assertRaises(ValidationError):  # no account, but says they paid only part
            services.record_expense.sync(self.by, date=self.today, amount=10, category=self.category, description="x",
                                         paid_by=self.director, paid_by_amount=4)
