"use client";

import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";

import { ApiError, isSold, modelName, priceLabel, sendInquiry, whatsappUrl } from "@/lib/api";
import type { ProductSummary } from "@/lib/types";

type Errors = Partial<Record<"full_name" | "email" | "phone" | "form", string>>;

const PHONE = /^[0-9+()\-.\s]{6,40}$/;

/**
 * The request form. It replaces checkout entirely: nothing is paid online, the
 * store receives the request and calls the customer back.
 *
 * With `product`, the watch is fixed and shown as a small plate. With
 * `choices`, the customer may pick one (or none, for a general inquiry).
 */
export function InquiryForm({
  product = null,
  choices = [],
  initialChoice = "",
  storePhone,
  submitLabel = "Request this watch",
}: {
  product?: ProductSummary | null;
  choices?: ProductSummary[];
  initialChoice?: string;
  storePhone: string | null;
  submitLabel?: string;
}) {
  const ids = useId();
  const [choice, setChoice] = useState(initialChoice);
  const [errors, setErrors] = useState<Errors>({});
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const chosen = product ?? choices.find((item) => item.slug === choice) ?? null;
  const whatsapp = whatsappUrl(
    storePhone,
    chosen
      ? `Hello, I am interested in the ${chosen.name}.`
      : "Hello, I have a question about a watch.",
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (key: string) => String(data.get(key) ?? "").trim();

    const next: Errors = {};
    if (value("full_name").length < 2) next.full_name = "Please enter your full name.";
    if (!/^\S+@\S+\.\S+$/.test(value("email"))) next.email = "Please enter a valid email address.";
    if (!PHONE.test(value("phone")))
      next.phone = "Please enter a phone number we can call, digits only.";
    setErrors(next);
    if (Object.keys(next).length > 0) {
      event.currentTarget.querySelector<HTMLElement>("[aria-invalid='true']")?.focus();
      return;
    }

    setSending(true);
    try {
      await sendInquiry({
        full_name: value("full_name"),
        email: value("email"),
        phone: value("phone"),
        product_id: chosen?.id ?? null,
        message: value("message") || null,
      });
      setSent(true);
    } catch (cause) {
      setErrors({
        form:
          cause instanceof ApiError && cause.status === 429
            ? "Too many requests in a short time. Please wait a few minutes and try again."
            : cause instanceof ApiError && cause.status < 500
              ? cause.message
              : "Your request could not be sent. Please check your connection and try again.",
      });
    } finally {
      setSending(false);
    }
  }

  if (sent) {
    return (
      <div role="status" className="py-6">
        <svg
          viewBox="0 0 48 48"
          aria-hidden
          className="size-12 text-clay"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        >
          <circle
            cx="24"
            cy="24"
            r="23"
            className="[stroke-dasharray:145] [stroke-dashoffset:145] animate-[draw_1.2s_var(--ease-luxury)_forwards]"
          />
          <path
            d="M15 24.5l6 6 12-13"
            className="[stroke-dasharray:30] [stroke-dashoffset:30] animate-[draw_0.8s_0.6s_var(--ease-luxury)_forwards]"
          />
        </svg>
        <h3
          className="fade-in mt-8 text-[2.5rem] leading-none"
          style={{ "--delay": "300ms" } as React.CSSProperties}
        >
          Thank you.
        </h3>
        <p
          className="fade-in mt-4 max-w-sm text-ink-muted"
          style={{ "--delay": "450ms" } as React.CSSProperties}
        >
          The store will contact you shortly
          {chosen ? ` about the ${modelName(chosen)}` : ""}.
        </p>
        {whatsapp && (
          <p
            className="fade-in mt-10 text-sm text-ink-subtle"
            style={{ "--delay": "650ms" } as React.CSSProperties}
          >
            Need a faster response?{" "}
            <a
              href={whatsapp}
              target="_blank"
              rel="noreferrer noopener"
              className="link-under text-ink-muted"
            >
              Contact us on WhatsApp
            </a>
          </p>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-8">
      {product ? (
        <WatchPlate product={product} />
      ) : (
        choices.length > 0 && (
          <div>
            <label htmlFor={`${ids}-watch`} className="eyebrow block">
              Watch
            </label>
            <div className="relative">
              <select
                id={`${ids}-watch`}
                value={choice}
                onChange={(event) => setChoice(event.target.value)}
                className="line-field cursor-pointer appearance-none pr-8"
              >
                <option value="">No particular watch</option>
                {choices.map((item) => (
                  <option key={item.id} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
              <svg
                viewBox="0 0 12 8"
                aria-hidden
                className="pointer-events-none absolute top-1/2 right-1 h-2 w-3 -translate-y-1/2 text-clay"
                fill="none"
                stroke="currentColor"
              >
                <path d="M1 1l5 5 5-5" />
              </svg>
            </div>
          </div>
        )
      )}

      <Field
        id={`${ids}-name`}
        name="full_name"
        label="Full name"
        autoComplete="name"
        error={errors.full_name}
      />
      <div className="grid gap-8 sm:grid-cols-2">
        <Field
          id={`${ids}-email`}
          name="email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email}
        />
        <Field
          id={`${ids}-phone`}
          name="phone"
          label="Phone number"
          type="tel"
          autoComplete="tel"
          inputMode="tel"
          error={errors.phone}
        />
      </div>
      <div>
        <label htmlFor={`${ids}-message`} className="eyebrow flex justify-between">
          <span>Note</span>
          <span className="tracking-normal normal-case">Optional</span>
        </label>
        <textarea
          id={`${ids}-message`}
          name="message"
          rows={3}
          maxLength={2000}
          placeholder="Anything we should know: timing, questions, a preferred time to call."
          className="line-field resize-none"
        />
      </div>

      {errors.form && (
        <p role="alert" className="text-sm text-danger">
          {errors.form}
        </p>
      )}

      <div className="space-y-5 pt-2">
        <button type="submit" disabled={sending} className="btn btn-primary w-full">
          {sending ? "Sending your request…" : submitLabel}
        </button>
        <p className="text-center text-xs leading-relaxed text-ink-subtle">
          No payment is taken online. The store will contact you to confirm the details.
        </p>
        {whatsapp && (
          <p className="text-center text-xs text-ink-subtle">
            Need a faster response?{" "}
            <a
              href={whatsapp}
              target="_blank"
              rel="noreferrer noopener"
              className="link-under text-ink-muted"
            >
              Contact us on WhatsApp
            </a>
          </p>
        )}
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  error,
  ...input
}: {
  id: string;
  label: string;
  error?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="eyebrow block">
        {label}
      </label>
      <input
        id={id}
        required
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className="line-field"
        {...input}
      />
      {error && (
        <p id={`${id}-error`} className="mt-2 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

function WatchPlate({ product }: { product: ProductSummary }) {
  return (
    <div className="flex items-center gap-5 border-y border-line py-4">
      <div className="relative size-20 shrink-0 overflow-hidden bg-surface-muted">
        {product.primary_image && (
          <Image
            src={product.primary_image.url}
            alt=""
            fill
            sizes="80px"
            className="object-cover"
          />
        )}
      </div>
      <div className="min-w-0">
        <p className="maker">{product.brand?.name}</p>
        <p className="mt-1 truncate font-display text-xl">{modelName(product)}</p>
        <p className="figures mt-0.5 text-sm text-ink-muted">
          {isSold(product) ? "Sold" : priceLabel(product)}
        </p>
      </div>
    </div>
  );
}

/**
 * The product page's call to action: the inline button, a bar pinned to the
 * bottom of small screens, and the sheet they both open. A native <dialog>
 * gives focus trapping, Escape and the inert backdrop for free.
 */
export function RequestPanel({
  product,
  storePhone,
}: {
  product: ProductSummary;
  storePhone: string | null;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [closing, setClosing] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const sold = isSold(product);
  const label = sold ? "Request a similar piece" : "Request this watch";

  function open() {
    setClosing(false);
    dialogRef.current?.showModal();
  }

  function close() {
    setClosing(true);
    setTimeout(() => {
      dialogRef.current?.close();
      setClosing(false);
    }, 420);
  }

  // The pinned bar appears only once the inline button has scrolled away.
  const inlineRef = useRef<HTMLDivElement>(null);
  const [inlineVisible, setInlineVisible] = useState(true);
  useEffect(() => {
    const el = inlineRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setInlineVisible(entry.isIntersecting));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Arriving from the homepage's "Request this watch" opens the sheet directly.
  useEffect(() => {
    if (window.location.hash === "#request") dialogRef.current?.showModal();
  }, []);

  const whatsapp = whatsappUrl(storePhone, `Hello, I am interested in the ${product.name}.`);

  return (
    <>
      <div id="request" ref={inlineRef} className="scroll-mt-32 space-y-4">
        <button type="button" onClick={open} className="btn btn-primary w-full">
          {label}
        </button>
        {whatsapp && (
          <p className="text-center text-xs text-ink-subtle">
            Prefer to talk now?{" "}
            <a
              href={whatsapp}
              target="_blank"
              rel="noreferrer noopener"
              className="link-under text-ink-muted"
            >
              Message us on WhatsApp
            </a>
          </p>
        )}
      </div>

      {/* Pinned to the thumb on phones, so the request is never a scroll away. */}
      <div
        aria-hidden={inlineVisible}
        inert={inlineVisible}
        className={`fixed inset-x-0 bottom-0 z-20 border-t border-line bg-canvas/95 px-5 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-md transition-transform duration-700 ease-[var(--ease-luxury)] lg:hidden ${
          inlineVisible ? "translate-y-full" : ""
        }`}
      >
        <div className="flex items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="truncate font-display text-lg leading-tight">{modelName(product)}</p>
            <p className="figures text-xs text-ink-muted">{sold ? "Sold" : priceLabel(product)}</p>
          </div>
          <button type="button" onClick={open} className="btn btn-primary !min-h-12 !px-5">
            {sold ? "Request similar" : "Request"}
          </button>
        </div>
      </div>

      <dialog
        ref={dialogRef}
        aria-labelledby="request-title"
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
        onClick={(event) => event.target === dialogRef.current && close()}
        onClose={() => setFormKey((key) => key + 1)}
        data-closing={closing || undefined}
        className="request-sheet"
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-line px-6 py-5 sm:px-10">
            <p className="eyebrow">{sold ? "Similar piece" : "Private request"}</p>
            <button
              type="button"
              onClick={close}
              className="-mr-2 grid size-11 place-items-center"
              autoFocus
            >
              <span className="sr-only">Close</span>
              <svg
                viewBox="0 0 16 16"
                aria-hidden
                className="size-4"
                stroke="currentColor"
                fill="none"
              >
                <path d="M1 1l14 14M15 1L1 15" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-10 sm:px-10">
            {/* Once sent, the confirmation replaces the introduction. */}
            <div className="[&:has(+_div_[role=status])]:hidden">
              <h2 id="request-title" className="text-[2.4rem] leading-[1.02] sm:text-[2.8rem]">
                {sold ? "Find me one like this" : "Request this watch"}
              </h2>
              <p className="mt-4 mb-10 max-w-sm text-[0.95rem] text-ink-muted">
                {sold
                  ? "This piece has found its owner. Leave your details and the store will look for a similar watch for you."
                  : "Leave your details and the store will contact you personally to confirm availability and arrange the rest."}
              </p>
            </div>
            <div>
              <InquiryForm
                key={formKey}
                product={product}
                storePhone={storePhone}
                submitLabel={sold ? "Send request" : "Request this watch"}
              />
            </div>
          </div>
        </div>
      </dialog>
    </>
  );
}
