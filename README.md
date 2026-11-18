# Dakdot

Dakdot Creations' internal system: clients, projects, quotations, invoices, receipts, expenses and account balances.

## Run it locally (Windows)

```powershell
uv sync
copy dakdot\.envtemp dakdot\.env     # skip if dakdot\.env already exists
uv run python manage.py migrate
uv run python manage.py seed_basics
uv run python manage.py createsuperuser
uv run uvicorn dakdot.asgi:application --reload --port 8000
```

Open http://localhost:8000, sign in, then:

1. **Money → Accounts**: set each account's opening balance and the date you counted it.
2. **Admin → Company settings**: check the phone, email, terms and upload the logo.
3. **Admin → Staff**: add the others with their role (Admin, Finance or Staff).

Subscriptions are billed by `uv run python manage.py bill_subscriptions`. Run it once a day: Windows Task
Scheduler locally, cron (or the host's scheduler) on the server.

## API for our products

Each product's app reads its subscribers, invoices and payments from `/api/v1/`. An admin makes a key per product
(and per server) under **Admin → API keys**; the key is shown once. The app sends it as
`Authorization: Bearer <key>`, from its server only. The everyday check is
`GET /api/v1/customers/<their-id-in-your-app>/status`, which answers whether that customer is active and paid up.
Full reference: `/api/v1/docs` (signed-in admins).

Frontend changes: `cd static`, `pnpm install`, then `pnpm dev` while working or `pnpm build` before committing.

See `CLAUDE.md` for how the code is organised.
