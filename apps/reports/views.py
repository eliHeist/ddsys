from apps.core.http import arender, staff_required

from . import selectors


@staff_required()
async def dashboard(request):
    can_see_money = request.actor.is_superuser or request.staff.role in ("finance", "admin")
    return await arender(request, "reports/dashboard.html", await selectors.dashboard(can_see_money))


@staff_required()
async def search(request):
    query = request.GET.get("q", "").strip()
    return await arender(request, "reports/partials/_search_results.html",
                         {"groups": await selectors.search(query), "q": query})
