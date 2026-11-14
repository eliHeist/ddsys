# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repository.

Dakdot is the internal system of Dakdot Creations Limited (Kampala): clients, projects, quotations, invoices, receipts and
the money in Dakdot's accounts (bank, mobile money, cash). About four people use it. It follows the layout of
`garagebaker` (same author): async views, sync services, django-cotton-ui, Vite. `TIME_ZONE = Africa/Kampala`, currency UGX.

## Commands

Python deps: **uv** (`pyproject.toml` + `uv.lock`, Python >= 3.14).

```bash
uv sync
copy dakdot\.envtemp dakdot\.env            # then set SECRET_KEY (cp on macOS/Linux)
uv run python manage.py migrate
uv run python manage.py seed_basics         # company settings, Stanbic / MTN MoMo / Cash accounts, expense categories
uv run python manage.py createsuperuser
uv run uvicorn dakdot.asgi:application --reload --port 8000

# Tests: name the modules (apps/ has no __init__.py, so bare discovery misses them)
uv run python manage.py test apps.billing.tests apps.reports.test_pages
```

Frontend (`static/`, pnpm): `pnpm install`, `pnpm dev`, `pnpm build`. `prebuild` regenerates `src/cotton-ui.sources.css`
(never edit it); the build goes to `static/dist`, which Django serves and which is committed.

New apps: `uv run djs startapp apps.<name>` (djangosetupheist), then fix the URL in `dakdot/appsConfig.py`.

## Architecture

### Apps and URLs
Apps are listed **only** in `dakdot/appsConfig.py`; that list feeds `INSTALLED_APPS` and mounts each app's URLs
(`app/<x>/`, namespaced). `accounts/` (custom email-login `User`, allauth + MFA) sits at the root; the rest are in `apps/`:
`core` (company settings, staff roles, shared helpers and components), `clients`, `projects`, `billing` (quotations,
invoices, receipts), `finance` (accounts, transactions, expenses, transfers), `documents` (PDFs), `reports` (dashboard, search).

### Async views + sync services (the key pattern)
- Views are `async def`. Reads are in each app's `selectors.py` (async ORM). Writes go through `services`
  (`apps/billing/services/{quotations,invoices,receipts}.py`, `apps/finance/services.py`): plain sync functions with
  `@service` (apps/core/async_utils.py) + `@transaction.atomic`, so each runs as one transaction in a worker thread.
  Call `await svc(...)` from views, `svc.sync(...)` from tests and commands.
- Services check roles (`require_role`) and state and raise `ValidationError`; views only parse forms and render.
  `service_errors` turns those errors into a 422 fragment swapped into `#form-errors` (or the dialog).
- `apps/core/http.py`: `staff_required(*roles)` (sets `request.staff`, `request.actor`), `arender`, `form_page`,
  `avalidate`/`asave` (ModelForms touch the DB), `paginate`, `hx_redirect`, `redirect_with_message` (toast after a redirect).
- Roles: `StaffProfile.Role` = admin / finance / staff. Groups in `apps/core/permissions.py`: `ADMINS`, `MONEY`
  (finance + admin: issue invoices, record payments and expenses), `EVERYONE`. Superusers pass everything.

### Documents and money rules
- Numbers: `PREFIX + YY + DD + SEQ(3) + MM` (INV261000111 = 2026, 10th, first of the day, November), from
  `apps/core/mixins/numbering.py`. The number is made from the document's own `date`, inside the insert transaction.
- Quotations and invoices (`billing/models/base_document.py`) start as **drafts**: no number, no date, editable.
  Issuing sets today's date and the number and freezes them. Mistakes are fixed by voiding (keeps the number), never by deleting.
- Lines (`core.models.AbstractLine`): `is_lump_sum` rows ("Binding: 50,000") keep quantity 1 and print "-" for price and qty.
- A **receipt** is the only way client money comes in: `receipts.record_payment` creates the receipt (numbered from the
  payment date), a money-in `finance.Transaction` on the chosen account, and refreshes the invoice's paid amount/status.
  It stores invoice total / previously paid at that moment so reprints never change.
- Account balances are never stored: opening balance + valid transactions (`finance.selectors.balances`).
  Transactions are written only by services and voided with their receipt / expense / transfer, never deleted.
- History: `django-simple-history` on clients, projects, quotations, invoices, receipts, accounts and expenses.

### PDFs
`apps/documents/pdf.py` (the Dakdot look on fpdf2, DM Sans in `documents/fonts/dmsans/`) + `layouts.py` (invoice /
quotation, receipt, client statement). `documents:pdf` serves them inline. Drafts have no PDF.

### Templates / UI
Templates live **in each app** (`apps/<app>/templates/<app>/`, with `partials/`); keep files small and use components.
Shared pieces are in `apps/core/templates/`: `base.html` (app shell), `cotton/` (`<c-page-header>`, `<c-section>`,
`<c-status>`, `<c-list-toolbar>`, layouts, kit overrides), `core/_ui.html` partials (`#stat`, `#empty`, `#pager`),
`core/_action_dialog.html` (one data-driven dialog: `$dispatch('open-dialog', {...})`), `core/_scripts.html`
(Alpine: `actionDialog`, `lineEditor`). Root `templates/` only overrides allauth pages.
django-cotton-ui notes: Alpine bindings on components need `::`; don't pass `class` to `<c-ui.input>`/`select`/`textarea`.

### Tests
`apps/billing/tests.py` covers the money rules through services; `apps/reports/test_pages.py` renders every page and
PDF with real templates.
