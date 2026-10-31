import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { AuthCard, PasswordInput, PhoneInput } from "../components/authBits";
import { Alert, Button } from "../components/ui";
import { ApiError, api, errorMessage, type Owner } from "../lib/api";
import { ME_KEY } from "../lib/auth";
import { safeNext } from "../lib/format";

export default function Login() {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const next = safeNext(params.get("next"), "/account");

  const login = useMutation({
    mutationFn: () => api<{ user: Owner }>("/api/auth/login", { method: "POST", body: { phone, password } }),
    onSuccess: ({ user }) => {
      queryClient.setQueryData(ME_KEY, user);
      navigate(next, { replace: true });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate();
  };

  const issues = login.error instanceof ApiError ? login.error.issues : [];

  return (
    <AuthCard title="Log in" subtitle="Welcome back.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        {login.error && <Alert>{errorMessage(login.error)}</Alert>}
        <PhoneInput value={phone} onChange={setPhone} error={issues.find((i) => i.field === "phone")?.message} />
        <PasswordInput value={password} onChange={setPassword} />
        <Button type="submit" className="w-full" loading={login.isPending}>
          Log in
        </Button>
      </form>
      <div className="flex justify-between text-sm">
        <Link to="/forgot-password" className="font-medium text-brand">
          Forgot password?
        </Link>
        <Link to={`/register${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-brand">
          Create an account
        </Link>
      </div>
    </AuthCard>
  );
}
