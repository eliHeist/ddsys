from datetime import date
from decimal import Decimal

from django.db.models import Case, DecimalField, F, Q, Sum, When

from .models import Account, Expense, Transaction

SIGNED = Case(When(direction=Transaction.Direction.IN, then=F("amount")), default=-F("amount"),
              output_field=DecimalField(max_digits=14, decimal_places=2))


def with_balances(accounts):
    """Accounts annotated with `moved` (net of valid transactions); balance = opening_balance + moved."""
    return accounts.annotate(moved=Sum(Case(
        When(transactions__is_void=False, transactions__direction=Transaction.Direction.IN, then=F("transactions__amount")),
        When(transactions__is_void=False, transactions__direction=Transaction.Direction.OUT, then=-F("transactions__amount")),
        default=Decimal(0), output_field=DecimalField(max_digits=14, decimal_places=2))))


async def balances(include_inactive=False):
    accounts = Account.objects.all() if include_inactive else Account.objects.filter(is_active=True)
    rows = []
    async for account in with_balances(accounts):
        account.balance = account.opening_balance + (account.moved or 0)
        rows.append(account)
    return rows


async def account_ledger(account, start=None, end=None):
    """The account's transactions in date order with a running balance, starting from the opening balance."""
    running = account.opening_balance
    if start:
        before = await account.transactions.filter(is_void=False, date__lt=start).aaggregate(s=Sum(SIGNED))
        running += before["s"] or 0
    txns = account.transactions.select_related("receipt", "expense", "transfer").order_by("date", "created_at")
    if start:
        txns = txns.filter(date__gte=start)
    if end:
        txns = txns.filter(date__lte=end)
    rows = []
    async for txn in txns:
        if not txn.is_void:
            running += txn.signed_amount
        txn.running = running
        rows.append(txn)
    rows.reverse()  # newest first on screen
    return rows, running


def transactions_for(account_id="", kind="", start=None, end=None, query=""):
    txns = Transaction.objects.select_related("account", "receipt", "expense", "transfer")
    if account_id:
        txns = txns.filter(account_id=account_id)
    if kind:
        txns = txns.filter(kind=kind)
    if start:
        txns = txns.filter(date__gte=start)
    if end:
        txns = txns.filter(date__lte=end)
    if query:
        txns = txns.filter(Q(description__icontains=query) | Q(reference__icontains=query))
    return txns


def expenses_for(category_id="", project_id="", start=None, end=None, query=""):
    expenses = Expense.objects.select_related("account", "category", "project")
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if project_id:
        expenses = expenses.filter(project_id=project_id)
    if start:
        expenses = expenses.filter(date__gte=start)
    if end:
        expenses = expenses.filter(date__lte=end)
    if query:
        expenses = expenses.filter(Q(description__icontains=query) | Q(payee__icontains=query)
                                   | Q(reference__icontains=query))
    return expenses


async def month_totals(year, month):
    """Money in and out this month, transfers left out (they are neither)."""
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    base = Transaction.objects.filter(is_void=False, date__gte=start, date__lt=end).exclude(kind=Transaction.Kind.TRANSFER)
    money_in = (await base.filter(direction=Transaction.Direction.IN).aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    money_out = (await base.filter(direction=Transaction.Direction.OUT).aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    return {"in": money_in, "out": money_out, "net": money_in - money_out}
