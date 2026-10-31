import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { AuthCard, OtpInput, PasswordInput, PhoneInput, useCountdown } from "../components/authBits";
import { Alert, Button } from "../components/ui";
import { ApiError, api, errorMessage } from "../lib/api";

export default function ForgotPassword() {
  const [step, setStep] = useState<"phone" | "reset" | "done">("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const countdown = useCountdown();

  const sendCode = useMutation({
    mutationFn: () => api<{ resendAfterSeconds: number }>("/api/auth/password/reset/request", { method: "POST", body: { phone } }),
    onSuccess: (res) => {
      countdown.restart(res.resendAfterSeconds);
      setStep("reset");
    },
    onError: (error) => {
      // A code was already sent a moment ago: carry on and wait out the timer.
      if (error instanceof ApiError && error.code === "OTP_COOLDOWN") {
        countdown.restart(error.retryAfterSeconds ?? 60);
        setStep("reset");
      }
    },
  });

  const reset = useMutation({
    mutationFn: () => api("/api/auth/password/reset/confirm", { method: "POST", body: { phone, otp, newPassword } }),
    onSuccess: () => setStep("done"),
  });

  const onPhone = (event: FormEvent) => {
    event.preventDefault();
    sendCode.mutate();
  };
  const onReset = (event: FormEvent) => {
    event.preventDefault();
    reset.mutate();
  };

  const sendIssues = sendCode.error instanceof ApiError ? sendCode.error.issues : [];
  const resetIssues = reset.error instanceof ApiError ? reset.error.issues : [];
  const sendError = sendCode.error instanceof ApiError && sendCode.error.code === "OTP_COOLDOWN" ? null : sendCode.error;

  if (step === "done") {
    return (
      <AuthCard title="Password changed" subtitle="You have been logged out everywhere. Log in with your new password.">
        <Link
          to="/login"
          className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover"
        >
          Log in
        </Link>
      </AuthCard>
    );
  }

  if (step === "phone") {
    return (
      <AuthCard title="Reset your password" subtitle="We will text a code to the mobile number on your account.">
        <form onSubmit={onPhone} className="space-y-4" noValidate>
          {sendError && <Alert>{errorMessage(sendError)}</Alert>}
          <PhoneInput value={phone} onChange={setPhone} error={sendIssues.find((i) => i.field === "phone")?.message} />
          <Button type="submit" className="w-full" loading={sendCode.isPending}>
            Send code
          </Button>
        </form>
        <Link to="/login" className="text-sm font-medium text-brand">
          Back to log in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Choose a new password" subtitle={`If ${phone} has an account, a code is on its way.`}>
      <form onSubmit={onReset} className="space-y-4" noValidate>
        {reset.error && resetIssues.length === 0 && <Alert>{errorMessage(reset.error)}</Alert>}
        <OtpInput value={otp} onChange={setOtp} error={resetIssues.find((i) => i.field === "otp")?.message} />
        <PasswordInput
          label="New password"
          value={newPassword}
          onChange={setNewPassword}
          autoComplete="new-password"
          hint="At least 8 characters."
          error={resetIssues.find((i) => i.field === "newPassword")?.message}
        />
        <Button type="submit" className="w-full" loading={reset.isPending}>
          Change password
        </Button>
      </form>
      <div className="flex items-center justify-between text-sm">
        <button type="button" className="font-medium text-brand" onClick={() => setStep("phone")}>
          Change number
        </button>
        <Button variant="ghost" disabled={countdown.left > 0} loading={sendCode.isPending} onClick={() => sendCode.mutate()}>
          {countdown.left > 0 ? `Resend code in ${countdown.left}s` : "Resend code"}
        </Button>
      </div>
    </AuthCard>
  );
}
