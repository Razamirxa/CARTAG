import { useEffect, useState, type ReactNode } from "react";
import { Logo } from "./layouts";
import { TagArt } from "./TagArt";
import { Field, Input } from "./ui";

export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="mx-auto grid max-w-4xl overflow-hidden rounded-[1.75rem] border border-line bg-surface md:grid-cols-[0.9fr_1.1fr]">
      {/* The burgundy side is brand, not content, so it stays the same in light and dark mode. */}
      <aside
        className="relative hidden flex-col justify-between overflow-hidden p-9 md:flex"
        style={{ background: "#74152B", color: "#F5F1E8" }}
      >
        <Logo inverted />
        <TagArt colour="IVORY" className="mx-auto my-8 w-44 -rotate-6" />
        <p className="heading text-xl">Your number stays behind the buttons.</p>
      </aside>
      <div className="p-6 sm:p-10">
        <h1 className="heading text-3xl">{title}</h1>
        {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
        <div className="mt-6 space-y-4">{children}</div>
      </div>
    </div>
  );
}

export function PasswordInput({
  label = "Password",
  value,
  onChange,
  error,
  hint,
  autoComplete = "current-password",
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string | undefined;
  hint?: string;
  autoComplete?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <Field label={label} error={error} hint={hint}>
      <div className="relative">
        <Input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          className="pe-16"
          required
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="absolute inset-y-0 end-0 px-3 text-sm font-medium text-brand"
          aria-label={show ? "Hide password" : "Show password"}
        >
          {show ? "Hide" : "Show"}
        </button>
      </div>
    </Field>
  );
}

export function PhoneInput({
  value,
  onChange,
  error,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  error?: string | undefined;
  disabled?: boolean;
}) {
  return (
    <Field label="Mobile number" error={error} hint="A Pakistani mobile number, for example 0300 1234567">
      <Input
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="03XX XXXXXXX"
        disabled={disabled}
        required
      />
    </Field>
  );
}

export function OtpInput({ value, onChange, error }: { value: string; onChange: (value: string) => void; error?: string | undefined }) {
  return (
    <Field label="6-digit code" error={error} hint="We sent it as a text message. It is valid for 5 minutes.">
      <Input
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]{6}"
        maxLength={6}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
        className="text-center font-mono text-xl tracking-[0.4em]"
        required
      />
    </Field>
  );
}

/** Counts down from `seconds` to zero. Call `restart` after sending a new code. */
export function useCountdown() {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (left <= 0) return;
    const timer = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [left]);
  return { left, restart: (seconds: number) => setLeft(Math.max(0, Math.ceil(seconds))) };
}
