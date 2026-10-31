import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { OtpInput, PasswordInput, PhoneInput, useCountdown } from "../components/authBits";
import { Alert, Button, Card, PageHeader } from "../components/ui";
import { ApiError, api, errorMessage, type Owner } from "../lib/api";
import { ME_KEY, useMe } from "../lib/auth";
import { formatPkMobile } from "../lib/format";

export default function ChangePhone() {
  const me = useMe();
  const queryClient = useQueryClient();
  const countdown = useCountdown();
  const [step, setStep] = useState<"number" | "code" | "done">("number");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");

  const request = useMutation({
    mutationFn: () =>
      api<{ resendAfterSeconds: number }>("/api/me/phone/change/request", { method: "POST", body: { phone, password } }),
    onSuccess: (res) => {
      countdown.restart(res.resendAfterSeconds);
      setStep("code");
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "OTP_COOLDOWN") {
        countdown.restart(error.retryAfterSeconds ?? 60);
        setStep("code");
      }
    },
  });

  const confirm = useMutation({
    mutationFn: () => api<{ user: Owner }>("/api/me/phone/change/confirm", { method: "POST", body: { phone, otp } }),
    onSuccess: ({ user }) => {
      queryClient.setQueryData(ME_KEY, user);
      setStep("done");
    },
  });

  const onNumber = (event: FormEvent) => {
    event.preventDefault();
    request.mutate();
  };
  const onCode = (event: FormEvent) => {
    event.preventDefault();
    confirm.mutate();
  };

  const requestIssues = request.error instanceof ApiError ? request.error.issues : [];
  const requestError =
    request.error instanceof ApiError && request.error.code === "OTP_COOLDOWN" ? null : request.error;

  return (
    <div className="mx-auto max-w-md space-y-5">
      <Link to="/account" className="text-sm font-medium text-brand">
        ← My account
      </Link>
      <PageHeader title="Change mobile number" subtitle={me.data ? `Now: ${formatPkMobile(me.data.phone)}` : undefined} />

      {step === "done" && (
        <Alert tone="success">Your mobile number is changed. You stay signed in here, and your other devices were signed out.</Alert>
      )}

      {step === "number" && (
        <Card>
          <form onSubmit={onNumber} className="space-y-4" noValidate>
            {requestError && <Alert>{errorMessage(requestError)}</Alert>}
            <PhoneInput value={phone} onChange={setPhone} error={requestIssues.find((i) => i.field === "phone")?.message} />
            <PasswordInput label="Your password" value={password} onChange={setPassword} hint="We ask for it to make sure this is you." />
            <Button type="submit" className="w-full" loading={request.isPending}>
              Send code to the new number
            </Button>
          </form>
        </Card>
      )}

      {step === "code" && (
        <Card>
          <form onSubmit={onCode} className="space-y-4" noValidate>
            <p className="text-sm text-muted">If {phone} can be used, a code is on its way.</p>
            {confirm.error && <Alert>{errorMessage(confirm.error)}</Alert>}
            <OtpInput value={otp} onChange={setOtp} />
            <Button type="submit" className="w-full" loading={confirm.isPending} disabled={otp.length !== 6}>
              Save new number
            </Button>
          </form>
          <div className="mt-3 flex items-center justify-between text-sm">
            <button type="button" className="font-medium text-brand" onClick={() => setStep("number")}>
              Use a different number
            </button>
            <Button variant="ghost" disabled={countdown.left > 0} loading={request.isPending} onClick={() => request.mutate()}>
              {countdown.left > 0 ? `Resend code in ${countdown.left}s` : "Resend code"}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
