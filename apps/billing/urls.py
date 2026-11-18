from django.urls import path

from .views import invoices, quotations, receipts, subscriptions

app_name = "billing"

urlpatterns = [
    path("quotations/", quotations.quotation_list, name="quotations"),
    path("quotations/new/", quotations.quotation_create, name="quotation-new"),
    path("quotations/<int:pk>/", quotations.quotation_detail, name="quotation"),
    path("quotations/<int:pk>/edit/", quotations.quotation_edit, name="quotation-edit"),
    path("quotations/<int:pk>/issue/", quotations.quotation_issue, name="quotation-issue"),
    path("quotations/<int:pk>/accept/", quotations.quotation_decide, {"answer": "accepted"}, name="quotation-accept"),
    path("quotations/<int:pk>/decline/", quotations.quotation_decide, {"answer": "declined"}, name="quotation-decline"),
    path("quotations/<int:pk>/to-invoice/", quotations.quotation_convert, name="quotation-convert"),
    path("quotations/<int:pk>/void/", quotations.quotation_void, name="quotation-void"),
    path("quotations/<int:pk>/delete/", quotations.quotation_delete, name="quotation-delete"),

    path("invoices/", invoices.invoice_list, name="invoices"),
    path("invoices/new/", invoices.invoice_create, name="invoice-new"),
    path("invoices/<int:pk>/", invoices.invoice_detail, name="invoice"),
    path("invoices/<int:pk>/edit/", invoices.invoice_edit, name="invoice-edit"),
    path("invoices/<int:pk>/issue/", invoices.invoice_issue, name="invoice-issue"),
    path("invoices/<int:pk>/void/", invoices.invoice_void, name="invoice-void"),
    path("invoices/<int:pk>/delete/", invoices.invoice_delete, name="invoice-delete"),
    path("invoices/<int:pk>/pay/", invoices.invoice_pay, name="invoice-pay"),
    path("invoices/<int:pk>/apply-credit/", invoices.invoice_apply_credit, name="invoice-apply-credit"),

    path("subscriptions/", subscriptions.subscription_list, name="subscriptions"),
    path("subscriptions/new/", subscriptions.subscription_create, name="subscription-new"),
    path("subscriptions/<int:pk>/", subscriptions.subscription_detail, name="subscription"),
    path("subscriptions/<int:pk>/edit/", subscriptions.subscription_edit, name="subscription-edit"),
    path("subscriptions/<int:pk>/invoice-now/", subscriptions.subscription_invoice_now, name="subscription-invoice-now"),
    path("subscriptions/<int:pk>/pause/", subscriptions.subscription_status, {"status": "paused"}, name="subscription-pause"),
    path("subscriptions/<int:pk>/resume/", subscriptions.subscription_status, {"status": "active"}, name="subscription-resume"),
    path("subscriptions/<int:pk>/end/", subscriptions.subscription_status, {"status": "ended"}, name="subscription-end"),

    path("receipts/", receipts.receipt_list, name="receipts"),
    path("receipts/<int:pk>/", receipts.receipt_detail, name="receipt"),
    path("receipts/<int:pk>/void/", receipts.receipt_void, name="receipt-void"),
    path("receipts/<int:pk>/apply/", receipts.receipt_apply, name="receipt-apply"),
    path("deposits/new/<int:client_pk>/", receipts.deposit_new, name="deposit-new"),
    path("allocations/<int:pk>/remove/", receipts.allocation_remove, name="allocation-remove"),
]
