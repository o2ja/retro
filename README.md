# Retro Watches

Luxury pre-owned watch commerce platform for Retro Watches (Instagram [@retrowhatches.jo](https://www.instagram.com/retrowatches.jo/?__d=1%252F%252F)).

| | |
|---|---|
| **Storefront** | Next.js 16 (App Router), TypeScript, Tailwind v4 |
| **Backend** | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| **Database** | PostgreSQL (SQLite for local development) |
| **Status** | Storefront redesigned around inquiries: customers request a watch, the owner calls back |

Specifications live in `01_GLOBAL_RULES.md`, `02_FRONTEND_SPEC.md`,
`03_BACKEND_SPEC.md`, `04_PHASE_BUILD_PROMPTS.md` and
`05_IMPLEMENTATION_CHECKLIST.md`. Architecture decisions are recorded in
[`docs/DECISIONS.md`](docs/DECISIONS.md).

---

## Layout

```
backend/            FastAPI application
  app/
    core/           config, security, errors, rate limiting, enums, utils
    api/            public routes + admin routes (auth, catalog, commerce, content)
    services/       business logic: pricing, inventory, orders, catalog, audit
    payments/       provider abstraction + Stripe reference implementation
    models.py       all ORM models
    schemas.py      all request/response contracts
    seed.py         development seed (the real starting catalog)
  alembic/          migrations
  tests/            pytest suite
frontend/           Next.js storefront + admin dashboard
  app/              storefront routes; app/admin is the dashboard
  components/       storefront UI; components/admin is the dashboard kit
  lib/              typed API clients (public + admin), types, cart store
  public/products/  the owner's watch photography
docs/DECISIONS.md   architecture decision records
```

## Running it

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

cp .env.example .env
# Set SECRET_KEY:  python -c "import secrets; print(secrets.token_urlsafe(48))"
# Set ADMIN_PASSWORD (used once, by the seed).

.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m app.seed
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

API docs (development only): <http://127.0.0.1:8000/docs>

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev            # http://localhost:3000
```

### Admin dashboard

<http://localhost:3000/admin> — sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`
from the backend `.env` (the same values the seed used).

### Turning payments on

```bash
# backend/.env
PAYMENT_PROVIDER=stripe
PAYMENT_SECRET_KEY=sk_live_or_test_...
PAYMENT_WEBHOOK_SECRET=whsec_...
STOREFRONT_URL=https://your-domain
```

Point the provider's webhook at `POST /api/payments/webhook/stripe`. Until all
three are set the payment path returns 503 and no order can be marked paid.

### Checks

```bash
cd backend  && .venv/Scripts/python.exe -m pytest && .venv/Scripts/python.exe -m ruff check .
cd frontend && npm run lint && npm run build
```

## Things to know before changing anything

- **Customers request, they do not check out.** The storefront has no cart or
  card payment. "Request this watch" posts to `POST /api/public/inquiries`;
  requests appear under **Inquiries** in the dashboard. Set the contact phone in
  **Settings** to show the small "Contact us on WhatsApp" link.

- **The backend is the source of truth** for prices, discounts, stock, totals
  and payment state. The browser is never trusted with any of them.
- **No product data in the frontend.** Products come from the database through
  the API. Homepage content comes from the CMS tables, not from JSX.
- **`Product.price` may be NULL.** The starting catalog has estimated market
  values only; a watch with no selling price is shown as "price on request"
  until the owner sets one in the dashboard.
- **The cart never computes money.** It stores product ids and quantities;
  `POST /api/checkout/quote` produces every figure shown.
- **Payments need configuring before they work.** With `PAYMENT_PROVIDER`
  unset the whole payment path returns 503 by design. Set it to `stripe` with
  real keys to switch it on.
- **An order only becomes a sale through a verified provider response.** The
  browser landing on a success page proves nothing and is never trusted.
- **Stock is held when the order is opened**, not when payment clears. That is
  what prevents two people buying the same watch.
- **Every schema change needs an Alembic migration.** Never
  `Base.metadata.create_all` against a real database.
- **Never commit `.env`, `.env.local`, or a database file.**
