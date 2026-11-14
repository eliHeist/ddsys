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
]
