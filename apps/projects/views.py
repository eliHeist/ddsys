from django.shortcuts import aget_object_or_404
from django.urls import reverse

from apps.core.http import arender, form_page, paginate, staff_required, wants_partial

from . import selectors
from .forms import ProjectForm
from .models import Project


@staff_required()
async def project_list(request):
    status, query = request.GET.get("status", "open"), request.GET.get("q", "").strip()
    page = await paginate(selectors.projects_for(status, query), request)
    template = "projects/partials/_project_rows.html" if wants_partial(request, "project-rows") else "projects/project_list.html"
    return await arender(request, template, {"page_obj": page, "q": query, "status": status})


@staff_required()
async def project_detail(request, pk):
    project = await aget_object_or_404(Project.objects.select_related("client", "lead"), pk=pk)
    return await arender(request, "projects/project_detail.html", {
        "project": project, "money": await selectors.money_summary(project), **await selectors.documents(project)})


@staff_required()
async def project_create(request):
    initial = {"client": request.GET.get("client")} if request.GET.get("client") else None
    return await form_page(request, form_class=ProjectForm, title="New project", initial=initial,
                           cancel_url=reverse("projects:list"), success_url=lambda p: reverse("projects:detail", args=[p.pk]))


@staff_required()
async def project_edit(request, pk):
    project = await aget_object_or_404(Project.objects.select_related("client"), pk=pk)
    return await form_page(request, form_class=ProjectForm, instance=project, title=f"Edit {project.title}",
                           cancel_url=reverse("projects:detail", args=[pk]), success_url=reverse("projects:detail", args=[pk]))
