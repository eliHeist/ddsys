"""Billing services, grouped by document. Import the module you need:
`from apps.billing.services import quotations, invoices, receipts`.

Every public service is awaitable (`await invoices.issue_invoice(...)`) and runs as one transaction in a worker
thread (see apps/core/async_utils.py). Its plain version is `invoices.issue_invoice.sync(...)`, for tests and
management commands. Services check permissions and state themselves and raise ValidationError.
"""
