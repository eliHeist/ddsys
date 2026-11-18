from datetime import date

from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.billing.forms import void_dialog
from apps.core.http import (arender, avalidate, error_response, form_errors, form_page, hx_redirect, redirect_with_message, paginate,
                            service_errors, staff_required, wants_partial)
from apps.core.permissions import ADMINS, MONEY

from . import loans, selectors, services
from .forms import (AccountForm, AdjustmentForm, ExpenseForm, LoanForm, OtherIncomeForm, RepaymentForm, TransferForm,
                    repay_dialog)
from .models import Account, Expense, Loan, LoanRepayment, Transaction, Transfer


def _date(text):
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


@staff_required(*MONEY)
async def account_list(request):
    accounts = await selectors.balances(include_inactive=True)
    today = timezone.localdate()
    return await arender(request, "finance/account_list.html", {
        "accounts": accounts, "total": sum((a.balance for a in accounts if a.is_active), 0),
        "month": await selectors.month_totals(today.year, today.month), "today": today,
    })


@staff_required(*MONEY)
async def account_detail(request, pk):
    account = await aget_object_or_404(Account, pk=pk)
    start, end = _date(request.GET.get("from")), _date(request.GET.get("to"))
    rows, balance = await selectors.account_ledger(account, start, end)
    return await arender(request, "finance/account_detail.html", {
        "account": account, "rows": rows, "balance": balance, "start": start, "end": end})


@staff_required(*ADMINS)
async def account_create(request):
    return await form_page(request, form_class=AccountForm, title="New account", initial={"opening_date": timezone.localdate()},
                           cancel_url=reverse("finance:accounts"), success_url=lambda a: reverse("finance:account", args=[a.pk]))


@staff_required(*ADMINS)
async def account_edit(request, pk):
    account = await aget_object_or_404(Account, pk=pk)
    return await form_page(request, form_class=AccountForm, instance=account, title=f"Edit {account.name}",
                           cancel_url=reverse("finance:account", args=[pk]), success_url=reverse("finance:account", args=[pk]))


@staff_required(*MONEY)
async def transaction_list(request):
    filters = {"account_id": request.GET.get("account", ""), "kind": request.GET.get("kind", ""),
               "start": _date(request.GET.get("from")), "end": _date(request.GET.get("to")),
               "query": request.GET.get("q", "").strip()}
    page = await paginate(selectors.transactions_for(**filters), request, per_page=50)
    template = "finance/partials/_transaction_rows.html" if wants_partial(request, "transaction-rows") else "finance/transaction_list.html"
    return await arender(request, template, {
        "page_obj": page, "q": filters["query"], "filters": filters, "kinds": Transaction.Kind.choices,
        "accounts": [a async for a in Account.objects.all()]})


@staff_required(*MONEY)
async def expense_list(request):
    query = request.GET.get("q", "").strip()
    page = await paginate(selectors.expenses_for(query=query), request)
    template = "finance/partials/_expense_rows.html" if wants_partial(request, "expense-rows") else "finance/expense_list.html"
    return await arender(request, template, {"page_obj": page, "q": query})


async def _service_form(request, *, form_class, action, title, success, initial=None, files=False, submit="Save", **extra):
    """GET shows the form; a valid POST calls the service with the cleaned data and redirects to `success(result)`."""
    if request.method == "POST":
        form = form_class(request.POST, request.FILES if files else None)
        if not await avalidate(form):
            return await error_response(request, form_errors(form))
        result = await action(request.actor, **{k: v for k, v in form.cleaned_data.items() if v is not None or k != "fee"})
        return hx_redirect(request, success(result))
    form = form_class(initial={"date": timezone.localdate(), **(initial or {})})
    return await arender(request, "core/form.html", {"form": form, "title": title, "submit": submit, **extra})


@staff_required(*MONEY)
@service_errors
async def expense_create(request):
    return await _service_form(request, form_class=ExpenseForm, action=services.record_expense, title="Record an expense",
                               initial={"project": request.GET.get("project")}, files=True, submit="Record expense",
                               cancel_url=reverse("finance:expenses"), success=lambda e: reverse("finance:expense", args=[e.pk]))


@staff_required(*MONEY)
async def expense_detail(request, pk):
    expense = await aget_object_or_404(Expense.objects.select_related("account", "category", "project", "created_by",
                                                                      "loan"), pk=pk)
    undo = ("What is owed back for the part they paid is voided too (only while none of it has been paid back)."
            if expense.loan_id else "The money goes back into the account.")
    return await arender(request, "finance/expense_detail.html", {
        "expense": expense,
        "void_dialog": void_dialog("Void this expense", reverse("finance:expense-void", args=[pk]), "The expense")
        | {"message": f"{undo} The expense stays on record, marked void."},
    })


@staff_required(*MONEY)
@require_POST
@service_errors
async def expense_void(request, pk):
    expense = await aget_object_or_404(Expense, pk=pk)
    await services.void_expense(expense, request.actor, reason=request.POST.get("reason", ""))
    return redirect_with_message(request, reverse("finance:expense", args=[pk]), "Expense voided.")


@staff_required(*MONEY)
@service_errors
async def transfer_create(request):
    return await _service_form(request, form_class=TransferForm, action=services.record_transfer, title="Move money between accounts",
                               submit="Record transfer", cancel_url=reverse("finance:accounts"),
                               success=lambda t: reverse("finance:accounts"))


@staff_required(*MONEY)
@require_POST
@service_errors
async def transfer_void(request, pk):
    await services.void_transfer(await aget_object_or_404(Transfer, pk=pk), request.actor)
    return redirect_with_message(request, reverse("finance:transactions"), "Transfer voided.")


@staff_required(*MONEY)
@service_errors
async def income_create(request):
    return await _service_form(request, form_class=OtherIncomeForm, action=services.record_other_income,
                               title="Record other money in", initial={"project": request.GET.get("project")}, submit="Record", cancel_url=reverse("finance:accounts"),
                               success=lambda t: reverse("finance:account", args=[t.account_id]))


@staff_required(*ADMINS)
@service_errors
async def adjustment_create(request):
    return await _service_form(request, form_class=AdjustmentForm, action=services.record_adjustment,
                               title="Adjust an account", submit="Record adjustment", cancel_url=reverse("finance:accounts"),
                               initial={"account": request.GET.get("account")},
                               success=lambda t: reverse("finance:account", args=[t.account_id]))


@staff_required(*ADMINS)
@require_POST
@service_errors
async def transaction_void(request, pk):
    txn = await aget_object_or_404(Transaction, pk=pk)
    await services.void_transaction(txn, request.actor)
    return redirect_with_message(request, reverse("finance:account", args=[txn.account_id]), "Transaction voided.")


# ---------------------------------------------------------------- loans (services in loans.py)

@staff_required(*MONEY)
async def loan_list(request):
    status, query = request.GET.get("status", "owing"), request.GET.get("q", "").strip()
    template = "finance/partials/_loan_rows.html" if wants_partial(request, "loan-rows") else "finance/loan_list.html"
    return await arender(request, template, {
        "loans": await selectors.loans_for(status, query), "totals": await selectors.loan_totals(),
        "status": status, "q": query, "tabs": [("owing", "Still owed"), ("all", "All")]})


@staff_required(*MONEY)
@service_errors
async def loan_create(request):
    return await _service_form(request, form_class=LoanForm, action=loans.record_loan, title="Record a loan or top-up",
                               submit="Record", cancel_url=reverse("finance:loans"),
                               subtitle="Money someone put into a company account: a loan, or a top-up so the account could "
                                        "pay for something. If they paid a supplier straight from their own pocket, record "
                                        "the expense instead and say who paid.",
                               success=lambda loan: reverse("finance:loan", args=[loan.pk]))


@staff_required(*MONEY)
async def loan_detail(request, pk):
    loan = await selectors.loan_detail(pk)
    accounts = [a async for a in Account.objects.filter(is_active=True)]
    return await arender(request, "finance/loan_detail.html", {
        "loan": loan,
        "repay_dialog": repay_dialog(loan, accounts) if loan.owed > 0 else None,
        "void_dialog": void_dialog("Void this loan", reverse("finance:loan-void", args=[pk]), "The loan")
        | {"message": "The money leaves the account again. The loan stays on record, marked void."},
    })


@staff_required(*MONEY)
@require_POST
@service_errors
async def loan_repay(request, pk):
    loan = await aget_object_or_404(Loan, pk=pk)
    form = RepaymentForm(request.POST)
    if not await avalidate(form):
        return await error_response(request, form_errors(form))
    await loans.repay_loan(loan, request.actor, **form.cleaned_data)
    return redirect_with_message(request, reverse("finance:loan", args=[pk]),
                                 "Reimbursement recorded." if loan.paid_costs_directly else "Repayment recorded.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def loan_must_repay(request, pk):
    must_repay = request.POST.get("must_repay") == "1"
    await loans.set_must_repay(await aget_object_or_404(Loan, pk=pk), request.actor, must_repay=must_repay)
    return redirect_with_message(request, reverse("finance:loan", args=[pk]),
                                 "Marked as to be refunded." if must_repay else "Marked as not to be refunded.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def loan_void(request, pk):
    await loans.void_loan(await aget_object_or_404(Loan, pk=pk), request.actor, reason=request.POST.get("reason", ""))
    return redirect_with_message(request, reverse("finance:loan", args=[pk]), "Loan voided.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def repayment_void(request, pk):
    repayment = await aget_object_or_404(LoanRepayment, pk=pk)
    await loans.void_repayment(repayment, request.actor, reason=request.POST.get("reason", ""))
    return redirect_with_message(request, reverse("finance:loan", args=[repayment.loan_id]), "Payment back voided.")
