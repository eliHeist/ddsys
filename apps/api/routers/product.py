from decimal import Decimal

from django.utils import timezone
from ninja import Router

from apps.billing.models import Subscription

from ..schemas import HealthOut, ProductOut

router = Router(tags=["Product"])


@router.get("/health", auth=None, response=HealthOut, summary="Is the API up? (no key needed)")
async def health(request):
    return {"status": "ok", "time": timezone.now()}


@router.get("/product", response=ProductOut, summary="The product this key belongs to")
async def product(request):
    product = request.auth.product
    active = [s async for s in Subscription.objects.filter(project=product, status=Subscription.Status.ACTIVE)
              .prefetch_related("lines")]
    return {"id": product.pk, "code": product.code, "title": product.title, "status": product.status,
            "active_subscriptions": len(active), "monthly_value": sum((s.monthly_value for s in active), Decimal(0))}
