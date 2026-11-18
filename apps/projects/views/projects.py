from django.shortcuts import aget_object_or_404
from django.urls import reverse

from apps.billing.selectors import product_subscriptions
from apps.core.http import arender, form_page, paginate, staff_required, wants_partial

from .. import selectors
from ..forms import ProjectForm
from ..models import Project

Kind = Project.Kind


async def _list(request, *, kinds, title, products):
    status, query = request.GET.get("status", "open"), request.GET.get("q", "").strip()
    page = await paginate(selectors.projects_for(status, query, kinds), request)
    template = "projects/partials/_project_rows.html" if wants_partial(request, "project-rows") else "projects/project_list.html"
    return await arender(request, template, {"page_obj": page, "q": query, "status": status, "title": title,
                                             "products": products})


@staff_required()
async def project_list(request):
    """Client work and Dakdot's internal projects."""
    return await _list(request, kinds=(Kind.CLIENT, Kind.INTERNAL), title="Projects", products=False)


@staff_required()
async def product_list(request):
    """Dakdot's own products: what they earn (subscriptions, invoices, other income) and what they cost."""
    return await _list(request, kinds=(Kind.PRODUCT,), title="Products", products=True)


@staff_required()
async def project_detail(request, pk):
    project = await aget_object_or_404(Project.objects.select_related("client", "lead"), pk=pk)
    if project.is_product:
        request.nav_url = reverse("projects:products")
    context = {"project": project, "money": await selectors.money_summary(project), **await selectors.documents(project),
               **await selectors.secrets(project)}
    if project.is_product or project.kind == Kind.CLIENT:
        context |= await product_subscriptions(project)
    return await arender(request, "projects/project_detail.html", context)


@staff_required()
async def project_create(request):
    kind = request.GET.get("kind") if request.GET.get("kind") in Kind.values else Kind.CLIENT
    initial = {"kind": Kind.CLIENT if request.GET.get("client") else kind, "client": request.GET.get("client")}
    back = reverse("projects:products") if kind == Kind.PRODUCT else reverse("projects:list")
    return await form_page(request, form_class=ProjectForm, title="New product" if kind == Kind.PRODUCT else "New project",
                           initial=initial, cancel_url=back, success_url=lambda p: reverse("projects:detail", args=[p.pk]))


@staff_required()
async def project_edit(request, pk):
    project = await aget_object_or_404(Project.objects.select_related("client"), pk=pk)
    return await form_page(request, form_class=ProjectForm, instance=project, title=f"Edit {project.title}",
                           cancel_url=reverse("projects:detail", args=[pk]), success_url=reverse("projects:detail", args=[pk]))
