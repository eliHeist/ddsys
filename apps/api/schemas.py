"""What the API returns. Money is a decimal string ("150000.00") so no precision is lost; dates are ISO 8601."""

from datetime import date, datetime
from decimal import Decimal

from django.urls import reverse
from ninja import Schema


class ClientOut(Schema):
    id: int
    name: str
    contact_person: str
    email: str
    phone: str


class LineOut(Schema):
    description: str
    note: str
    quantity: Decimal
    unit_price: Decimal
    is_lump_sum: bool
    amount: Decimal


class ProductOut(Schema):
    id: int
    code: str
    title: str
    status: str
    active_subscriptions: int
    monthly_value: Decimal


class SubscriptionOut(Schema):
    id: int
    external_ref: str
    title: str
    status: str
    interval_months: int
    start_date: date
    next_invoice_date: date | None
    end_date: date | None
    currency: str
    amount: Decimal
    monthly_value: Decimal
    paid_through: date | None
    owing: Decimal
    overdue_invoices: int
    paid_up: bool
    client: ClientOut
    lines: list[LineOut]
    updated_at: datetime

    @staticmethod
    def resolve_next_invoice_date(obj):
        return obj.next_invoice_date if obj.status == "active" else None

    @staticmethod
    def resolve_owing(obj):
        return obj.owing or Decimal(0)

    @staticmethod
    def resolve_paid_up(obj):
        return not obj.overdue_invoices

    @staticmethod
    def resolve_lines(obj):
        return list(obj.lines.all())


class CustomerStatusOut(Schema):
    """The quick check a product's app makes: may this customer use the product?"""

    external_ref: str
    client: ClientOut | None
    has_active_subscription: bool
    paid_up: bool
    paid_through: date | None
    owing: Decimal
    subscriptions: list[SubscriptionOut]


class ReceiptOut(Schema):
    id: int
    number: str
    status: str
    date: date
    amount: Decimal
    invoice_id: int | None  # None for a deposit (money paid before its invoice)
    invoice_number: str | None
    credit: Decimal  # the part not yet used on an invoice
    reference: str
    received_from: str
    updated_at: datetime
    pdf_url: str

    @staticmethod
    def resolve_invoice_number(obj):
        return obj.invoice.number if obj.invoice_id else None

    @staticmethod
    def resolve_credit(obj):
        return getattr(obj, "credit", 0) if obj.status == "valid" else 0

    @staticmethod
    def resolve_pdf_url(obj):
        return reverse("api-v1:receipt_pdf", args=[obj.pk])


class InvoiceOut(Schema):
    id: int
    number: str
    status: str
    date: date | None
    due_date: date | None
    currency: str
    total: Decimal
    amount_paid: Decimal
    balance: Decimal
    period_start: date | None
    period_end: date | None
    subscription_id: int | None
    client: ClientOut
    updated_at: datetime
    pdf_url: str

    @staticmethod
    def resolve_pdf_url(obj):
        return reverse("api-v1:invoice_pdf", args=[obj.pk])


class InvoiceDetailOut(InvoiceOut):
    notes: str
    lines: list[LineOut]
    receipts: list[ReceiptOut]

    @staticmethod
    def resolve_lines(obj):
        return list(obj.lines.all())

    @staticmethod
    def resolve_receipts(obj):
        """The receipts that paid it: payments on it, and deposits applied to it."""
        return list({a.receipt_id: a.receipt for a in obj.allocations.all()}.values())


class HealthOut(Schema):
    status: str
    time: datetime
