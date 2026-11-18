from datetime import datetime

from django.shortcuts import aget_object_or_404
from ninja import Router
from ninja.pagination import paginate

from .. import selectors
from ..schemas import SubscriptionOut

router = Router(tags=["Subscriptions"])


@router.get("/subscriptions", response=list[SubscriptionOut], summary="The product's subscribers")
@paginate
async def list_subscriptions(request, status: str | None = None, external_ref: str | None = None,
                             client_id: int | None = None, updated_since: datetime | None = None):
    """Filter by `status` (active / paused / ended), the customer's `external_ref` (their ID in your app),
    `client_id`, or `updated_since` to sync only what changed."""
    qs = selectors.subscriptions(request.auth.product)
    if status:
        qs = qs.filter(status=status)
    if external_ref:
        qs = qs.filter(external_ref=external_ref)
    if client_id:
        qs = qs.filter(client_id=client_id)
    if updated_since:
        qs = qs.filter(updated_at__gte=updated_since)
    return qs


@router.get("/subscriptions/{subscription_id}", response=SubscriptionOut)
async def get_subscription(request, subscription_id: int):
    return await aget_object_or_404(selectors.subscriptions(request.auth.product), pk=subscription_id)
