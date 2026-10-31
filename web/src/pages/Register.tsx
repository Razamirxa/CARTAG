import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { AuthCard, PasswordInput, PhoneInput } from "../components/authBits";
import { Alert, Button, Field, Input } from "../components/ui";
import { ApiError, api, errorMessage, type Owner } from "../lib/api";
import { ME_KEY } from "../lib/auth";
import { safeNext } from "../lib/format";

export default function Register() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const next = safeNext(params.get("next"), "/account");

  const register = useMutation({
    mutationFn: () => api<{ user: Owner }>("/api/auth/register", { method: "POST", body: { phone, name, password } }),
    onSuccess: ({ user }) => {
      queryClient.setQueryData(ME_KEY, user);
      navigate(next, { replace: true });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    register.mutate();
  };

  const issues = register.error instanceof ApiError ? register.error.issues : [];
  const fieldError = (field: string) => issues.find((i) => i.field === field)?.message;

  return (
    <AuthCard title="Create your account" subtitle="You will confirm your mobile number with a code when you turn on your first tag.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        {register.error && issues.length === 0 && <Alert>{errorMessage(register.error)}</Alert>}
        <Field label="Your name" error={fieldError("name")}>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} required />
        </Field>
        <PhoneInput value={phone} onChange={setPhone} error={fieldError("phone")} />
        <PasswordInput
          label="Choose a password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          hint="At least 8 characters."
          error={fieldError("password")}
        />
        <Button type="submit" className="w-full" loading={register.isPending}>
          Create account
        </Button>
      </form>
      <div className="flex justify-between text-sm">
        <Link to={`/login${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-brand">
          I already have an account
        </Link>
        <Link to="/forgot-password" className="font-medium text-brand">
          Forgot password?
        </Link>
      </div>
    </AuthCard>
  );
}
