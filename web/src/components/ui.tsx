import {
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import type { StockStatus, TagStatus } from "../lib/api";

export const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(" ");

/* ---------- buttons ---------- */

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
  primary: "bg-brand text-on-brand hover:bg-brand-hover",
  secondary: "border border-line bg-surface text-ink hover:bg-subtle",
  danger: "bg-danger text-surface hover:opacity-90",
  ghost: "text-brand hover:bg-subtle",
};

export function Button({
  variant = "primary",
  loading = false,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-55",
        variants[variant],
        className,
      )}
      {...rest}
    >
      {loading && <Spinner small />}
      {children}
    </button>
  );
}

/** A link that looks like a button. */
export const linkButton = (variant: Variant = "primary", extra?: string) =>
  cx(
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold transition-colors",
    variants[variant],
    extra,
  );

/** Two-step button for risky actions: first click asks, second click does it. No browser dialogs. */
export function ConfirmButton({
  label,
  confirmLabel = "Yes, do it",
  onConfirm,
  loading,
  variant = "danger",
}: {
  label: string;
  confirmLabel?: string;
  onConfirm: () => void;
  loading?: boolean;
  variant?: Variant;
}) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <Button variant="secondary" onClick={() => setAsking(true)}>
        {label}
      </Button>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button
        variant={variant}
        loading={loading}
        onClick={() => {
          onConfirm();
          setAsking(false);
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="ghost" onClick={() => setAsking(false)}>
        Cancel
      </Button>
    </span>
  );
}

/* ---------- form controls ---------- */

const control =
  "block w-full min-h-11 rounded-[0.7rem] border border-line bg-surface px-3.5 py-2 text-base text-ink placeholder:text-muted/70 focus:border-brand";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(control, className)} {...rest} />;
}

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(control, className)} {...rest} />;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(control, "min-h-28 font-mono text-sm", className)} {...rest} />;
}

/** The label wraps the control, so the two are linked without ids. */
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: ReactNode;
  error?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-semibold">{label}</span>
        {children}
      </label>
      {hint && !error && <p className="mt-1.5 text-sm text-muted">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1.5 text-sm font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** An on/off switch. */
export function Toggle({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className={cx("flex cursor-pointer items-start gap-3 py-2", disabled && "cursor-not-allowed opacity-60")}>
      <span className="relative mt-0.5 inline-flex h-7 w-12 shrink-0">
        <input
          type="checkbox"
          role="switch"
          className="peer absolute inset-0 size-full cursor-pointer opacity-0"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="pointer-events-none absolute inset-0 rounded-full border border-line bg-subtle transition-colors peer-checked:border-brand peer-checked:bg-brand peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand" />
        <span className="pointer-events-none absolute start-1 top-1 size-5 rounded-full bg-surface shadow-[0_1px_2px_rgba(0,0,0,0.3)] transition-transform peer-checked:translate-x-5 rtl:peer-checked:-translate-x-5" />
      </span>
      <span>
        <span className="block text-sm font-semibold">{label}</span>
        {hint && <span className="block text-sm text-muted">{hint}</span>}
      </span>
    </label>
  );
}

/* ---------- display ---------- */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cx("rounded-[1.25rem] border border-line bg-surface p-5 sm:p-6", className)}>{children}</section>;
}

type Tone = "neutral" | "success" | "warn" | "danger" | "brand";
const tones: Record<Tone, string> = {
  neutral: "bg-subtle text-muted",
  success: "bg-success-bg text-success",
  warn: "bg-warn-bg text-warn",
  danger: "bg-danger-bg text-danger",
  brand: "bg-[color-mix(in_srgb,var(--c-brand)_13%,transparent)] text-brand",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cx("inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold", tones[tone])}>{children}</span>;
}

const statusTone: Record<TagStatus, Tone> = { NOT_ACTIVE: "neutral", ACTIVE: "success", TURNED_OFF: "warn", RETIRED: "danger" };
const statusLabel: Record<TagStatus, string> = {
  NOT_ACTIVE: "Not active",
  ACTIVE: "Active",
  TURNED_OFF: "Turned off",
  RETIRED: "Retired",
};

export function StatusBadge({ status }: { status: TagStatus }) {
  return <Badge tone={statusTone[status]}>{statusLabel[status]}</Badge>;
}

const stockTone: Record<StockStatus, Tone> = { IN_STOCK: "neutral", RESERVED: "brand", SOLD: "success", DAMAGED: "danger", REPLACED: "warn" };
const stockLabel: Record<StockStatus, string> = {
  IN_STOCK: "In stock",
  RESERVED: "Reserved",
  SOLD: "Sold",
  DAMAGED: "Damaged",
  REPLACED: "Replaced",
};

export function StockBadge({ stock }: { stock: StockStatus }) {
  return <Badge tone={stockTone[stock]}>{stockLabel[stock]}</Badge>;
}

const alertTone = {
  danger: "border-danger bg-danger-bg text-danger",
  success: "border-success bg-success-bg text-success",
  warn: "border-warn bg-warn-bg text-warn",
};

/** A message with a coloured edge, so the kind of message reads before the words do. */
export function Alert({ tone = "danger", children }: { tone?: "danger" | "success" | "warn"; children: ReactNode }) {
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cx("rounded-xl border-s-4 px-4 py-3 text-sm font-medium", alertTone[tone])}>
      {children}
    </div>
  );
}

export function Spinner({ small }: { small?: boolean }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cx("inline-block animate-spin rounded-full border-2 border-current border-t-transparent", small ? "size-4" : "size-6")}
    />
  );
}

export function Loading() {
  return (
    <div className="flex justify-center p-10 text-muted">
      <Spinner />
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="heading text-3xl sm:text-4xl">{title}</h1>
        {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="mt-4 flex items-center justify-between gap-3 text-sm text-muted">
      <span className="tabular">
        {total.toLocaleString()} total, page {page} of {pages}
      </span>
      <span className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Next
        </Button>
      </span>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-[1.25rem] border border-dashed border-line p-8 text-center text-muted">{children}</p>;
}
