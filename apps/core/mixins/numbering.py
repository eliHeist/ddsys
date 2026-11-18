from django.db import IntegrityError, transaction
from django.db.models.functions import Length
from django.utils import timezone


FIRST_SEQUENCE = 500  # each day's count starts here, so a client never sees "001" on a document


def format_number(prefix, on_date, sequence):
    """PREFIX + YY + DD + SEQ(3) + MM, e.g. INV261050011: 2026, the 10th, the first of the day (500), November."""
    return f"{prefix}{on_date:%y}{on_date:%d}{sequence:03d}{on_date:%m}"


def generate_document_number(prefix, model_cls, field_name="number", on_date=None):
    """The next free number for `on_date` (today if not given). The count restarts at 500 every day.

    Must run inside the transaction that saves the document, so the row lock holds until the insert.
    """
    on_date = on_date or timezone.localdate()
    day_prefix = f"{prefix}{on_date:%y}{on_date:%d}"
    month = f"{on_date:%m}"
    last_number = (
        model_cls.objects.select_for_update()
        .filter(**{f"{field_name}__startswith": day_prefix, f"{field_name}__endswith": month})
        .annotate(num_len=Length(field_name))
        .order_by("-num_len", f"-{field_name}")  # length first, so seq 1000 sorts after 999
        .values_list(field_name, flat=True)
        .first()
    )
    sequence = int(last_number[len(day_prefix):-2]) + 1 if last_number else FIRST_SEQUENCE
    return format_number(prefix, on_date, sequence)


class NumberedMixin:
    """Gives a document its number the first time it is saved with `number_ready` true.

    Drafts are saved without a number, so deleting a draft never leaves a gap. The number uses the
    document's own date (`number_date_field`), so a payment entered a day late still gets the day it
    was received. If two saves collide, the unique constraint rejects one and it tries again.
    """

    number_prefix = ""
    number_field = "number"
    number_date_field = "date"

    @property
    def number_ready(self):
        return True

    def save(self, *args, **kwargs):
        if getattr(self, self.number_field) or not self.number_ready:
            return super().save(*args, **kwargs)  # pyright: ignore[reportAttributeAccessIssue]
        on_date = getattr(self, self.number_date_field, None)
        for attempt in range(5):
            try:
                with transaction.atomic():
                    number = generate_document_number(self.number_prefix, type(self), self.number_field, on_date)
                    setattr(self, self.number_field, number)
                    if kwargs.get("update_fields") is not None:
                        kwargs["update_fields"] = {*kwargs["update_fields"], self.number_field}
                    return super().save(*args, **kwargs)  # pyright: ignore[reportAttributeAccessIssue]
            except IntegrityError:
                setattr(self, self.number_field, "")
                if attempt == 4:
                    raise
