import functools
import json

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render

from .models import StaffProfile


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


async def arender(request, template, context=None, *, status=None, headers=None):
    """Template rendering is sync and templates may touch lazy attributes, so run it in the sync thread."""
    response = await sync_to_async(render)(request, template, context or {}, status=status)
    for key, value in (headers or {}).items():
        response[key] = value
    return response


def toast(message, variant="success"):
    """HX-Trigger header that shows a toast in <c-ui.toast.container> (variant: info, success, warning, error)."""
    return {"HX-Trigger": json.dumps({"toast": {"message": message, "variant": variant}})}


def redirect_with_message(request, url, message, level="success"):
    """Redirect and show `message` as a toast on the next page (HX-Redirect reloads the page, so an HX-Trigger
    toast would be lost; Django's messages survive the reload and core/_scripts.html shows them)."""
    getattr(messages, level)(request, message)
    return hx_redirect(request, url)


def hx_redirect(request, url):
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return HttpResponseRedirect(url)


def form_errors(form):
    return [
        err if field == "__all__" else f"{field.replace('_', ' ').capitalize()}: {err}"
        for field, errors in form.errors.items()
        for err in errors
    ]


async def error_response(request, messages, status=422):
    """HTMX swaps the messages into #form-errors; plain requests get the same fragment."""
    headers = {"HX-Retarget": "#form-errors", "HX-Reswap": "innerHTML"} if is_htmx(request) else {}
    return await arender(request, "core/partials/errors.html", {"errors": list(messages)}, status=status, headers=headers)


def staff_required(*roles):
    """Login + active staff profile (+ optional role list). Sets request.actor and request.staff.
    Superusers without a profile get an admin one, so the first sign-in after createsuperuser works."""

    def decorator(view):
        @functools.wraps(view)
        async def wrapper(request, *args, **kwargs):
            user = await request.auser()
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            staff = await StaffProfile.objects.filter(user=user, is_active=True).afirst()
            if staff is None and user.is_superuser:
                staff, _ = await StaffProfile.objects.aget_or_create(user=user, defaults={"role": StaffProfile.Role.ADMIN})
            if staff is None or (roles and staff.role not in roles and not user.is_superuser):
                raise PermissionDenied
            staff.user = user  # also caches user.staff, so services can read the role without a query
            request.staff, request.actor = staff, user
            return await view(request, *args, **kwargs)

        return wrapper

    return decorator


def service_errors(view):
    """Turn a service's ValidationError into a 422 message fragment."""

    @functools.wraps(view)
    async def wrapper(request, *args, **kwargs):
        try:
            return await view(request, *args, **kwargs)
        except ValidationError as exc:
            return await error_response(request, exc.messages)

    return wrapper


async def avalidate(form):
    """ModelForm validation runs unique checks against the database, so do it off the event loop."""
    return await sync_to_async(form.is_valid)()


async def asave(form):
    return await sync_to_async(form.save)()


async def form_page(request, *, form_class, template="core/form.html", instance=None, success_url, title,
                    initial=None, extra=None, cancel_url=None, submit="Save"):
    """Generic create/edit page for a ModelForm. GET shows the form; a valid POST saves and redirects."""
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=instance)
        if await avalidate(form):
            obj = await asave(form)
            return hx_redirect(request, success_url(obj) if callable(success_url) else success_url)
        status = 422
    else:
        form, status = form_class(instance=instance, initial=initial or {}), None
    context = {"form": form, "title": title, "cancel_url": cancel_url, "submit": submit, **(extra or {})}
    return await arender(request, template, context, status=status)


class Page:
    """Just enough of Django's Page for the pager partial, built without a sync paginator."""

    def __init__(self, items, number, count, per_page):
        self.object_list, self.number = items, number
        self.paginator = type("Paginator", (), {"count": count, "num_pages": max(1, -(-count // per_page))})()
        self.has_previous, self.has_next = number > 1, number < self.paginator.num_pages
        self.previous_page_number, self.next_page_number = number - 1, number + 1

    def __iter__(self):
        return iter(self.object_list)


async def paginate(queryset, request, per_page=25):
    """Async pagination: `?page=N` over any queryset (already ordered and select_related)."""
    try:
        number = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        number = 1
    count = await queryset.acount()
    number = min(number, max(1, -(-count // per_page)))
    start = (number - 1) * per_page
    return Page([row async for row in queryset[start:start + per_page]], number, count, per_page)


def wants_partial(request, target):
    """True when an HTMX request is refreshing just the element with this id (live search, filters)."""
    return is_htmx(request) and request.headers.get("HX-Target") == target
