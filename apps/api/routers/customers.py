from decimal import Decimal

from ninja import Router

from apps.billing.models import Subscription

from .. import selectors
from ..schemas import CustomerStatusOut

router = Router(tags=["Customers"])


@router.get("/customers/{external_ref}/status", response=CustomerStatusOut,
            summary="May this customer use the product? (by their ID in your app)")
async def customer_status(request, external_ref: str):
    """`paid_up` is false while any of the customer's invoices is past its due date and unpaid.
    `paid_through` is the end of the latest period that has been paid in full. An unknown `external_ref`
    returns no subscriptions and `has_active_subscription: false`."""
    subs = [s async for s in selectors.subscriptions(request.auth.product).filter(external_ref=external_ref)]
    paid = [s.paid_through for s in subs if s.paid_through]
    return {
        "external_ref": external_ref,
        "client": subs[0].client if subs else None,
        "has_active_subscription": any(s.status == Subscription.Status.ACTIVE for s in subs),
        "paid_up": all(not s.overdue_invoices for s in subs),
        "paid_through": max(paid, default=None) if paid else None,
        "owing": sum((s.owing or Decimal(0) for s in subs), Decimal(0)),
        "subscriptions": subs,
    }


