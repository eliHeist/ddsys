from django.urls import path

from .views import invoices, quotations, receipts

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

    path("receipts/", receipts.receipt_list, name="receipts"),
    path("receipts/<int:pk>/", receipts.receipt_detail, name="receipt"),
    path("receipts/<int:pk>/void/", receipts.receipt_void, name="receipt-void"),
]
