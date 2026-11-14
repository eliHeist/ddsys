from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

LINE_FIELDS = ("description", "note", "quantity", "unit_price", "is_lump_sum")


def clean_line(spec):
    """A line spec (dict) checked and normalised. Lump-sum lines keep quantity 1."""
    description = (spec.get("description") or "").strip()
    if not description:
        raise ValidationError("Every line needs a description.")
    quantity = Decimal(spec.get("quantity") or 1)
    unit_price = Decimal(spec.get("unit_price") or 0)
    is_lump_sum = bool(spec.get("is_lump_sum"))
    if is_lump_sum:
        quantity = Decimal(1)
    if quantity <= 0:
        raise ValidationError(f'"{description}": the quantity must be more than 0.')
    if unit_price < 0:
        raise ValidationError(f'"{description}": the price cannot be negative.')
    return {"description": description[:255], "note": (spec.get("note") or "").strip()[:255],
            "quantity": quantity, "unit_price": unit_price, "is_lump_sum": is_lump_sum}


def replace_lines(document, line_model, parent_field, specs):
    """Swap a draft's lines for `specs` and recalculate its total."""
    cleaned = [clean_line(spec) for spec in specs]
    if not cleaned:
        raise ValidationError("Add at least one line.")
    line_model.objects.filter(**{parent_field: document}).delete()
    line_model.objects.bulk_create(
        [line_model(**{parent_field: document}, sort_order=i, **spec) for i, spec in enumerate(cleaned)]
    )
    document.recalculate()


def copy_lines(source, line_model, parent_field, target):
    line_model.objects.bulk_create([
        line_model(**{parent_field: target}, sort_order=line.sort_order,
                   **{f: getattr(line, f) for f in LINE_FIELDS})
        for line in source.lines.all()
    ])
    target.recalculate()


def assert_draft(document):
    if not document.is_draft:
        raise ValidationError(f"{document.label} is {document.get_status_display().lower()}: only drafts can be changed.")


def assert_project_matches(client, project):
    if project is not None and project.client_id != client.pk:
        raise ValidationError(f"The project “{project.title}” belongs to {project.client}, not {client}.")


def today():
    return timezone.localdate()


def days_from(start, days):
    return start + timedelta(days=days)
