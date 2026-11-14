from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Invoice, InvoiceLine, Quotation, QuotationLine, Receipt


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


class QuotationLineInline(admin.TabularInline):
    model = QuotationLine
    extra = 0


# Read-mostly: documents change through the app's services, which keep totals, numbers and money in step.
@admin.register(Invoice)
class InvoiceAdmin(SimpleHistoryAdmin):
    list_display = ("label", "client", "date", "status", "total", "amount_paid")
    list_filter = ("status",)
    search_fields = ("number", "client__name")
    inlines = (InvoiceLineInline,)
    readonly_fields = ("number", "status", "total", "amount_paid", "issued_at", "voided_at")


@admin.register(Quotation)
class QuotationAdmin(SimpleHistoryAdmin):
    list_display = ("label", "client", "date", "status", "total")
    list_filter = ("status",)
    search_fields = ("number", "client__name")
    inlines = (QuotationLineInline,)
    readonly_fields = ("number", "status", "total", "issued_at", "voided_at")


@admin.register(Receipt)
class ReceiptAdmin(SimpleHistoryAdmin):
    list_display = ("number", "invoice", "date", "amount", "account", "status")
    list_filter = ("status", "account")
    search_fields = ("number", "invoice__number", "received_from", "reference")
    readonly_fields = ("number", "status", "amount", "invoice", "account", "invoice_total", "previously_paid")
