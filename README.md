# CARTAG

A QR tag that lets someone reach the owner. The person who scans it uses the phone camera; no app is needed.

```
cartag/      the API: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL
alembic/     database migrations
tests/       pytest suite (runs against its own database)
web/         the website: React, Vite, Tailwind
hamza given/ the client's scope document (CARTAG Lean V1)
```

## Run it locally

1. Install [uv](https://docs.astral.sh/uv/), Node 22 or newer, and PostgreSQL 17. Create two empty databases:
   `smarttag` and `smarttag_test`.
2. Copy `.env.example` to `.env` and fill it in. Make the secrets with `openssl rand -hex 32`.
3. Install, then create the tables:

```text
uv sync
npm install
uv run alembic upgrade head
```

4. Create a team login (the password is asked for, never put on the command line):

```text
uv run python -m cartag.cli create-admin --email you@example.com --name "Your Name"
```

5. Start the API and the website together: `npm run dev`
   The site is at http://localhost:5173 and the team panel at http://localhost:5173/admin.
   API docs (development only) are at http://localhost:4000/api/docs.

In development no SMS is sent. The one-time code is written to the `cartag.sms` log. Plain `uvicorn` does not switch that
logger on, so start the API with logging enabled, for example:

```text
uv run python -c "import logging,uvicorn; logging.basicConfig(level=logging.INFO); uvicorn.run('cartag.main:app', port=4000)"
```

### Windows: folder names containing `&`

npm scripts run through `cmd.exe` on Windows, and `cmd.exe` breaks on a path containing `&`. Rename the folder, or tell
npm to use Git Bash:

```text
npm config set script-shell "C:\Program Files\Git\bin\bash.exe"
```

The Python commands (`uv run ...`) are not affected.

## Checks

```text
uv run pytest            tests (needs the smarttag_test database)
uv run ruff check .      lint
npm run typecheck        web
npm run lint             web
npm run build            web
```

Tests build their schema with the real Alembic migrations and refuse to run against any database whose name does not end
in `_test`. One test fails if `models.py` and the migrations disagree.

## Changing the database

Edit `cartag/models.py`, then `uv run alembic revision --autogenerate -m "what changed"`. Read the new file in
`alembic/versions/` before applying it with `uv run alembic upgrade head`. If autogenerate writes a `CheckConstraint`
twice for an enum column, delete the duplicate lines.

## How the pieces fit

- **Tag code**: 10 random characters. The QR holds `https://<domain>/t/<CODE>` in upper case, which makes a smaller QR.
  The serial number (000001) is for the team panel and the printer only and never appears in a URL.
- **Tag states**: Not active, Active, Turned off (by the owner, can be turned on again), Retired (by staff, for good,
  the code is never reused). There is no way to move a tag to another owner.
- **Stock** is tracked separately: in stock, reserved, sold, damaged, replaced. **Only a tag marked sold can be turned
  on**, so nobody can claim an unsold tag on a shop shelf.
- **Scan page** `/t/<CODE>`: plain HTML from the server (about 3 KB, no JavaScript), English first with an Urdu switch.
  It shows the owner's name and two buttons, Call Owner and WhatsApp Owner. **The phone number is never printed as text**;
  it only sits inside the two links. Emergency Mode (blood group, one emergency contact) shows only when the owner turns it on.
- **Accounts**: mobile number and password. The mobile is confirmed with a one-time code when a tag is turned on, not at
  sign-in. Forgot password, changing the number and closing the account (team approves it) are included.
- **Shop**: twelve products (3 sizes x 4 colours). The server prices every order from the database and copies the
  items into the order, so later price changes never rewrite history. Cash on delivery works now.
- **Online payment**: an order is marked paid only when the payment provider calls our webhook with a valid signature
  and the right amount. A confirmation that arrives twice changes nothing. A provider is one class in
  `cartag/services/payments.py`; `PAYMENT_PROVIDER=mock` is a pretend one for development and is refused in production.
- **Sessions**: server-side, httpOnly cookie, only a hash is stored. Customers and team have separate cookies.
- **Passwords**: argon2id. Logins lock for 15 minutes after 5 failures, for unknown accounts too.
- **One-time codes**: hashed, 5 minutes, 5 attempts, per-phone and per-IP limits.
- **Print files**: SVG and EPS (one file per tag, in a ZIP), PDF (one page per tag, 5,000 tags per file) and a CSV with
  serial, code and link. All are drawn from the same QR matrix.

## Before you print anything

1. Decide the final domain and set `PUBLIC_BASE_URL`. Every batch remembers the domain it was made with.
2. Generate a small batch (20 tags) in **QR batches**, export it, and print a sample on the real material.
3. Scan the samples with several phones. The batch page shows the size of one QR module at your tag size (about 0.33 mm
   or more is needed).
4. Only then generate and export the real batch (the plan is 5,000, to be confirmed).

## Going live (checklist)

- `APP_ENV=production`, `PUBLIC_BASE_URL` on https, a real `SMS_PROVIDER` (the app refuses to start with `console`).
- `TRUST_PROXY=1` behind Nginx.
- Build the website (`npm run build`), run `uv run alembic upgrade head`, then
  `uv run uvicorn cartag.main:app --host 127.0.0.1 --port 4000`. The API serves `web/dist` itself.
- Back up the database daily.

## Preview deploy on Render

`render.yaml`, `Dockerfile` and `docker-start.sh` deploy a free preview from GitHub: a web service and a PostgreSQL
database. It runs with `APP_ENV=development` because production needs a real SMS provider first. The free web service
sleeps when idle and the free database expires after 30 days, so use it for demos only and never print tags that point
at its address. The first admin comes from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (Render generates the password; read it in
the service's Environment tab). One-time codes show in the service's Logs tab.

## Build status against the scope document

| Area | Status |
|---|---|
| Unique QR codes, batches, print files | Done |
| Tag states, stock status, retire | Done |
| Scan page (English and Urdu), Emergency Mode | Done |
| Accounts, activation code, change mobile, close account | Done |
| Team panel: batches, tags, customers, closing requests, activity | Done (one team role so far) |
| Website shop: 12 products, basket, checkout, orders, order history, cash on delivery | Done (prices are placeholders) |
| Team panel: orders, courier and tracking, cash collected, refunds, product prices | Done (one team role so far) |
| Automatic online payment: signed-webhook flow, retry, refunds | Done with a pretend provider; the real one needs a merchant account |
| Team roles (Admin, Operations, Finance, Support), stock intake, dispatch check | Next |
| Courier connection | After the courier is chosen |
| Real SMS provider | After the provider is chosen |
