from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("accounts/", views.account_list, name="accounts"),
    path("accounts/new/", views.account_create, name="account-new"),
    path("accounts/<int:pk>/", views.account_detail, name="account"),
    path("accounts/<int:pk>/edit/", views.account_edit, name="account-edit"),
    path("transactions/", views.transaction_list, name="transactions"),
    path("transactions/<int:pk>/void/", views.transaction_void, name="transaction-void"),
    path("expenses/", views.expense_list, name="expenses"),
    path("expenses/new/", views.expense_create, name="expense-new"),
    path("expenses/<int:pk>/", views.expense_detail, name="expense"),
    path("expenses/<int:pk>/void/", views.expense_void, name="expense-void"),
    path("transfers/new/", views.transfer_create, name="transfer-new"),
    path("transfers/<int:pk>/void/", views.transfer_void, name="transfer-void"),
    path("income/new/", views.income_create, name="income-new"),
    path("adjustments/new/", views.adjustment_create, name="adjustment-new"),
    path("loans/", views.loan_list, name="loans"),
    path("loans/new/", views.loan_create, name="loan-new"),
    path("loans/<int:pk>/", views.loan_detail, name="loan"),
    path("loans/<int:pk>/repay/", views.loan_repay, name="loan-repay"),
    path("loans/<int:pk>/must-repay/", views.loan_must_repay, name="loan-must-repay"),
    path("loans/<int:pk>/void/", views.loan_void, name="loan-void"),
    path("repayments/<int:pk>/void/", views.repayment_void, name="repayment-void"),
]
