import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { PasswordInput } from "../components/authBits";
import { Alert, Button, Card, Field, Loading, PageHeader, Textarea } from "../components/ui";
import { api, errorMessage, type DeletionRequest } from "../lib/api";
import { formatDateTime } from "../lib/format";

const KEY = ["my-delete-request"] as const;

export default function DeleteAccount() {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");

  const current = useQuery({
    queryKey: KEY,
    queryFn: async () => (await api<{ request: DeletionRequest | null }>("/api/me/delete-request")).request,
  });

  const send = useMutation({
    mutationFn: () => api<{ request: DeletionRequest }>("/api/me/delete-request", { method: "POST", body: { password, reason } }),
    onSuccess: ({ request }) => {
      setPassword("");
      queryClient.setQueryData(KEY, request);
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send.mutate();
  };

  if (current.isPending) return <Loading />;

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <Link to="/account" className="text-sm font-medium text-brand">
        ← My account
      </Link>
      <PageHeader title="Close my account" />

      <Card>
        <h2 className="font-semibold">What happens</h2>
        <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-muted">
          <li>Our team checks your request and approves it.</li>
          <li>Your tags are turned off for good and cannot be used again, and your contact card is removed.</li>
          <li>We keep only the records we need for orders and accounts.</li>
        </ul>
      </Card>

      {current.data ? (
        <Alert tone="warn">
          You asked us to close your account on {formatDateTime(current.data.requestedAt)}. We will look at it soon. Until then
          everything keeps working.
        </Alert>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          {send.error && <Alert>{errorMessage(send.error)}</Alert>}
          <PasswordInput label="Your password" value={password} onChange={setPassword} hint="We ask for it to make sure this is you." />
          <Field label="Why are you leaving? (optional)">
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
              className="min-h-24 font-sans"
            />
          </Field>
          <Button type="submit" variant="danger" loading={send.isPending}>
            Ask to close my account
          </Button>
        </form>
      )}
    </div>
  );
}
