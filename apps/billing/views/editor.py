"""The quotation and invoice editor: one page for both, since they share client, project, lines and terms."""

from django.urls import reverse

from apps.billing.forms import DocumentForm, lines_for_editor, parse_lines
from apps.core.http import arender, avalidate, error_response, form_errors, hx_redirect
from apps.core.models import CompanySettings
from apps.projects.models import Project

KINDS = {
    "quotation": {"date_field": "valid_until", "date_label": "Valid until", "terms": "quotation_terms",
                  "list": "billing:quotations", "detail": "billing:quotation", "title": "quotation"},
    "invoice": {"date_field": "due_date", "date_label": "Due date", "terms": "invoice_terms",
                "list": "billing:invoices", "detail": "billing:invoice", "title": "invoice"},
}


async def editor_page(request, kind, *, document=None, create, update):
    """GET shows the editor; POST saves the draft through `create(...)` or `update(document, ...)`."""
    cfg = KINDS[kind]
    if request.method == "POST":
        form = DocumentForm(request.POST, date_label=cfg["date_label"])
        if not await avalidate(form):
            return await error_response(request, form_errors(form))
        data = form.cleaned_data
        fields = {"client": data["client"], "project": data["project"], "lines": parse_lines(request.POST),
                  "notes": data["notes"], "terms": data["terms"], cfg["date_field"]: data["date_limit"]}
        saved = await (update(document, request.actor, **fields) if document else create(request.actor, **fields))
        return hx_redirect(request, reverse(cfg["detail"], args=[saved.pk]))

    if document:
        initial = {"client": document.client_id, "project": document.project_id, "notes": document.notes,
                   "terms": document.terms, "date_limit": getattr(document, cfg["date_field"])}
        rows = lines_for_editor([line async for line in document.lines.all()])
    else:
        settings = await CompanySettings.aload()
        initial = {"client": request.GET.get("client"), "project": request.GET.get("project"),
                   "terms": getattr(settings, cfg["terms"])}
        if initial["project"] and not initial["client"]:
            project = await Project.objects.filter(pk=initial["project"]).afirst()
            initial["client"] = project.client_id if project else None
        rows = []
    form = DocumentForm(initial=initial, date_label=cfg["date_label"])
    return await arender(request, "billing/document_form.html", {
        "form": form, "kind": kind, "document": document, "rows": rows,
        "title": f"Edit {document.label}" if document else f"New {cfg['title']}",
        "cancel_url": reverse(cfg["detail"], args=[document.pk]) if document else reverse(cfg["list"]),
    })
