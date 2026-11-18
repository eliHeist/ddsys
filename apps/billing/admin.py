from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Allocation, Invoice, InvoiceLine, Quotation, QuotationLine, Receipt


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


class AllocationInline(admin.TabularInline):
    model = Allocation
    fk_name = "receipt"
    extra = 0
    can_delete = False
    readonly_fields = ("invoice", "amount", "date", "created_by")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Receipt)
class ReceiptAdmin(SimpleHistoryAdmin):
    list_display = ("number", "client", "invoice", "date", "amount", "account", "status")
    list_filter = ("status", "account")
    search_fields = ("number", "invoice__number", "client__name", "received_from", "reference")
    readonly_fields = ("number", "status", "amount", "client", "invoice", "quotation", "project", "account",
                       "invoice_total", "previously_paid")
    inlines = (AllocationInline,)
