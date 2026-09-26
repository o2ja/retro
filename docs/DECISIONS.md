# Architecture Decisions — Obaidi Time

Short records of choices that are not obvious from the code. Add to this file
whenever a decision would otherwise have to be reverse-engineered later.

---

## 1. Stack

Next.js (App Router, TypeScript, Tailwind v4) for the storefront and, later, the
admin dashboard. FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL for the backend.
This is what `03_BACKEND_SPEC.md` specifies, and the repository was empty, so
nothing had to be preserved.

## 2. Database: PostgreSQL target, SQLite for local development

`DATABASE_URL` decides the engine. Production and staging use PostgreSQL
(`postgresql+psycopg://…`). Development defaults to SQLite so the project runs
with no local database server.

The cost of that convenience is contained in two places:

- `app/db.py` defines a `Money` column type that stores `NUMERIC(12,2)` on
  PostgreSQL and a fixed-precision **string** on SQLite. Money never becomes a
  float, on either engine.
- Alembic runs with `render_as_batch=True` on SQLite, because SQLite cannot
  `ALTER` most things in place.

Enums are stored as validated strings (`native_enum=False`), not native
PostgreSQL enum types, so adding a status later is an ordinary migration.

## 3. Money is a decimal string on the wire

The API serialises prices as decimal strings (`"20000.00"`), not JSON numbers.
JavaScript has no decimal type; a float round-trip on a $20,000 watch is a real
bug. `lib/types.ts` types them as `string` and the UI formats with
`Intl.NumberFormat`.

## 4. `price` is nullable — "price on request"

The starting catalog (`Brand_Obaidi_Time.md`) lists **estimated market values**,
not selling prices. On the owner's instruction the nine seeded watches are now
listed at those market values, but the columns stay separate and `price` stays
nullable — a watch with no price still renders as "price on request" with an
enquiry CTA instead of a buy button, and `SeedProduct.price` overrides the
default per watch. So:

- `Product.price` — the admin-controlled selling price. NULL until set.
- `Product.compare_at_price` — a previous/list price, shown struck through.
- `Product.estimated_market_price` — reference valuation, never used to sell.

When `price` is NULL the API returns `price_on_request: true` and no number.

## 5. Availability is derived, never stored

`Availability` (`IN_STOCK` / `LOW_STOCK` / `OUT_OF_STOCK` / `SOLD` / `HIDDEN`)
is computed from `Product.active`, `Inventory.quantity` and
`low_stock_threshold`. There is no status column to drift out of sync.

`Product.is_unique` marks a one-of-a-kind pre-owned piece. At zero stock a
unique piece reads `SOLD` rather than `OUT_OF_STOCK`, and it is never reported
as low stock — one unit *is* the whole stock.

## 6. Two kinds of promotion

- **Automatic** (`code IS NULL`) — applied to matching products across the
  catalog and reflected in listed prices and `/api/public/offers`.
- **Coded** (`code` set) — only applied when a customer enters the code, and
  always validated server-side via `POST /api/public/promotions/check`.

A promotion with no product and no category targeting covers the whole catalog.
When several automatic promotions match a product, the largest discount wins.

Promotions are deactivated, never deleted: past orders reference them.

## 7. Admin auth is a signed cookie, not a JWT

`itsdangerous` signs `{"sub": admin_id}` into an HTTP-only, SameSite=Lax cookie
with a max age. No token library, no refresh-token machinery, and rotating
`SECRET_KEY` invalidates every session. Passwords are Argon2id
(`argon2-cffi`), rehashed on login when parameters change.

Login failures always return the same message, so accounts cannot be enumerated,
and logins are rate limited per IP.

There is one admin role. A permission matrix can be added when a second kind of
admin actually exists.

## 8. Rate limiting is in-process

`app/core/ratelimit.py` keeps sliding-window counters in memory. That means
limits are per worker process. Marked with a `ponytail:` comment; move the
counters to Redis when the API runs on more than one process.

## 9. Payments: abstraction now, provider in Phase 4

`app/payments/` defines `PaymentProvider` (create session, verify, parse
webhook, refund) plus `UnconfiguredProvider`, whose every method raises 503.
There is deliberately **no** code path in the repository that can mark an order
paid. Phase 4 registers a real provider in `_PROVIDERS`.

## 10. Order status and payment status are separate columns

`Order.order_status` and `Order.payment_status` never merge.
`ORDER_STATUS_TRANSITIONS` in `app/core/enums.py` is the whole state machine;
`app/services/orders.py` refuses anything not in it, writes an
`OrderStatusHistory` row and an `AuditLog` entry, and restores inventory when a
stock-committed order is cancelled or refunded.

## 11. Order items carry a purchase snapshot

`OrderItem` stores product name, brand, SKU, reference and unit price at the
time of purchase. A past order is never reconstructed from the live product row,
because products get renamed and repriced.

## 12. Models, schemas and admin routes are grouped, not split per entity

All ORM models live in `app/models.py` and all Pydantic contracts in
`app/schemas.py`; admin routes are grouped by area (`auth`, `catalog`,
`commerce`, `content`) rather than one file per entity. The schema is one
cohesive unit and reads better together than across twenty near-empty modules.

Response models own their own ORM-to-payload mapping (`.build(...)`), which is
why endpoints stay thin and cannot accidentally leak an internal column.

## 13. Entities intentionally *not* created

- `PostCategory` — `Post.category` is a plain indexed string. A table would buy
  nothing until posts need shared, managed taxonomies.
- `CustomerAddress` — orders carry a shipping snapshot. Add it when customer
  accounts with saved addresses actually exist.

## 14. Seed data is the real catalog, with nothing invented

`python -m app.seed` loads the nine watches from `Brand_Obaidi_Time.md`. Fields
absent from that document (movement, crystal, water resistance, reference
numbers) stay empty rather than being filled with plausible-looking text. Sold
pieces are seeded at quantity 0, not deleted. No customers, orders or sales are
seeded, so analytics can never show fabricated numbers.

The seed is idempotent and matches rows by SKU/slug.

## 15. `ADMIN_PASSWORD`, not `ADMIN_PASSWORD_HASH`

The backend spec suggested storing a password hash in the environment. Instead
`ADMIN_EMAIL` / `ADMIN_PASSWORD` are read **only** by `python -m app.seed`,
which hashes the password into the database. The running application never reads
`ADMIN_PASSWORD`, and there is no hash to keep in sync in two places.


---

## 16. Cart lives in the browser, money lives on the server

The cart is `localStorage` holding `{product_id, quantity}` and nothing else,
read through `useSyncExternalStore` (`frontend/lib/cart.tsx`). Every figure the
customer sees comes from `POST /api/checkout/quote`, which re-reads prices,
promotions and stock from the database.

Tampering with `localStorage` can change *what* is in the bag. It cannot change
what the bag costs, because no price is ever posted back — the request schema
(`CartLineIn`) accepts only an id and a quantity, and extra fields are dropped.

## 17. The order is opened before payment, and it holds the stock

**Revised in Phase 4.** `POST /api/checkout/payment-session` revalidates the
cart, writes the order in `PENDING_PAYMENT`, and decrements inventory *at that
moment*. Only then does it ask the provider for a session.

Holding stock at order-open is what makes overselling impossible: `adjust` locks
the inventory row and refuses to go below zero, so the second person trying to
buy the last watch is refused at checkout rather than after their card clears.
The alternative the spec sketched — decrement only on confirmed payment — leaves
a window in which two people can both pay for one watch, which for
one-of-a-kind pieces is the worst possible failure.

An order in `PENDING_PAYMENT` is not a sale. Only `confirm_payment`, driven by a
verified provider response, sets `payment_status = PAID`. If the payment fails,
is cancelled, or the admin cancels, `orders.transition` returns the stock.

## 18. Shipping is quoted at zero

There are no shipping rates or zones defined yet, so `checkout.SHIPPING_TOTAL`
is `0.00` and the UI says shipping is arranged on confirmation rather than
implying free delivery. Marked with a `ponytail:` comment; replace with a rate
table when shipping is actually charged.

## 19. Product images are static files, not uploads

The owner's nine photographs live in `frontend/public/products/<slug>.png` and
`ProductImage.url` points at them. The filename is derived from the product slug
in the seed, so the two cannot drift apart. Phase 3 replaces this with real
uploads to object storage; the `ProductImage` table does not change.

## 20. Scroll reveals are CSS, not JavaScript

Section reveals use `animation-timeline: view()` inside an `@supports` guard
(`frontend/app/globals.css`). No IntersectionObserver, no observer component, no
layout thrash, and browsers without scroll-driven animations simply show the
content. A global `prefers-reduced-motion` block turns all of it off.

## 21. The newsletter does not claim a subscription

No newsletter provider is integrated, so the form hands the address to the
visitor's mail client and says exactly that. It never reports a successful
sign-up that did not happen. Swap `handleSubmit` for the provider call when one
exists; the loading, error and consent states are already there.

## 22. Contact is channels, not a form

There is no enquiry endpoint, and a form that silently goes nowhere is worse
than an email address that works. `/contact` renders the CMS-configured email,
phone and social links. Add the form when there is an endpoint behind it.


---

## 23. Stripe is the reference provider, and it brings no SDK

`app/payments/stripe.py` calls Stripe's REST API with `httpx` and verifies
webhook signatures with stdlib `hmac`/`hashlib`. No SDK to keep in step, no new
dependency.

It is registered only when `PAYMENT_PROVIDER=stripe` **and** `PAYMENT_SECRET_KEY`
is set. Otherwise `get_provider()` returns `UnconfiguredProvider` and every
payment path returns 503. Swapping processors means writing one class with four
methods and adding it to `_registry()`; nothing outside `app/payments/` changes.

Stripe is not available in every market. It is here because it is the
best-documented implementation of the abstraction, not because it is the final
choice — see "Known limitations" in the README.

## 24. Webhook safety: verified, bounded, idempotent

Three separate guards, in this order:

1. **Signature.** HMAC-SHA256 over `timestamp.payload` with the webhook secret,
   compared with `hmac.compare_digest`. A forged or wrongly-signed event is
   rejected before its body is parsed.
2. **Freshness.** A signature older than 300 seconds is rejected, which bounds
   replay of a captured-but-valid request.
3. **Idempotency.** `Payment.provider_event_id` is unique. An event id already
   stored returns 200 "already processed" without being applied again, so
   Stripe's retries cannot decrement stock or confirm an order twice.

On top of that, `confirm_payment` refuses any PAID result whose amount or
currency does not match the order it was written against.

## 25. Order confirmation is verified, never assumed

`GET /api/orders/{order_number}` requires the matching email — an order number
alone reveals nothing. If the payment is still `PENDING` the endpoint asks the
provider directly rather than trusting that the customer landed on a success
URL. The page renders three honest outcomes: paid, pending, or failed.

The response model (`PublicOrderOut`) is a separate schema from the admin one:
no internal ids, no provider references, no payment rows.

## 26. Analytics are aggregated, never estimated

`app/services/analytics.py` is SQL aggregation over orders whose
`payment_status = PAID`. With no sales the dashboard reports zero and the charts
say "nothing recorded across these N days" — it never interpolates, projects or
fills a gap. Time series return one point per day *including zeros*, so a flat
line means "nothing happened", not "no data".

"Best selling" is units in paid orders. Nothing else is ever labelled best.

## 27. Dashboard charts are inline SVG with one hue

Every chart plots a single measure, so there is no series identity to encode and
no categorical palette to validate: one clay/bark hue, no legend, and every value
written as text beside its bar. A polyline and some rectangles do not need a
charting library, and not having one is one fewer thing to upgrade.

Status is always a word inside a border, never colour alone.

## 28. The admin auth gate is convenience, not security

`components/admin/shell.tsx` decides what to *render* by calling
`/api/admin/me`. It is not a security boundary — every admin endpoint
independently requires the signed session cookie, so a tampered client state
gets 401s and nothing else. The dashboard is also `robots: noindex`.
