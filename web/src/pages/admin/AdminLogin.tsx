import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { PasswordInput } from "../../components/authBits";
import { Logo } from "../../components/layouts";
import { Alert, Button, Card, Field, Input } from "../../components/ui";
import { api, errorMessage, type AdminUser } from "../../lib/api";
import { ADMIN_ME_KEY, useAdminMe } from "../../lib/auth";

export default function AdminLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const me = useAdminMe();

  const login = useMutation({
    mutationFn: () => api<{ admin: AdminUser }>("/api/admin/auth/login", { method: "POST", body: { email, password } }),
    onSuccess: ({ admin }) => {
      queryClient.setQueryData(ADMIN_ME_KEY, admin);
      navigate("/admin", { replace: true });
    },
  });

  if (me.data) return <Navigate to="/admin" replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate();
  };

  return (
    <div className="mx-auto max-w-sm px-4 pt-16">
      <div className="mb-6 flex justify-center">
        <Logo className="text-xl" />
      </div>
      <Card>
        <h1 className="heading text-2xl">Admin log in</h1>
        <form onSubmit={submit} className="mt-4 space-y-4" noValidate>
          {login.error && <Alert>{errorMessage(login.error)}</Alert>}
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </Field>
          <PasswordInput value={password} onChange={setPassword} />
          <Button type="submit" className="w-full" loading={login.isPending}>
            Log in
          </Button>
        </form>
      </Card>
    </div>
  );
}
