import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Alert, Badge, Button, Card, ConfirmButton, Empty, Field, Input, Loading, PageHeader, Select } from "../../components/ui";
import { api, errorMessage, type Page } from "../../lib/api";
import { formatDateTime, formatPkMobile } from "../../lib/format";

interface Item {
  id: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reason: string | null;
  requestedAt: string;
  decidedAt: string | null;
  note: string | null;
  user: { id: string; name: string; phone: string };
  tagCount: number;
}

function Request({ item }: { item: Item }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: (action: "approve" | "reject") =>
      api(`/api/admin/deletion-requests/${item.id}/${action}`, { method: "POST", body: { note } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
  const pending = item.status === "PENDING";

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{item.user.name}</p>
          <p className="text-sm text-muted">
            {item.user.phone.startsWith("deleted:") ? "Closed account" : formatPkMobile(item.user.phone)} · {item.tagCount} tag(s) ·
            asked {formatDateTime(item.requestedAt)}
          </p>
        </div>
        <Badge tone={pending ? "warn" : item.status === "APPROVED" ? "success" : "neutral"}>{item.status.toLowerCase()}</Badge>
      </div>
      {item.reason && <p className="mt-3 rounded-xl bg-subtle px-4 py-3 text-sm">“{item.reason}”</p>}
      {item.note && <p className="mt-2 text-sm text-muted">Team note: {item.note}</p>}

      {pending && (
        <div className="mt-4 space-y-3 border-t border-line pt-4">
          {decide.error && <Alert>{errorMessage(decide.error)}</Alert>}
          <p className="text-sm text-muted">
            Approving retires their tags for good, removes their contact card and wipes their name and number. This cannot be undone.
          </p>
          <Field label="Note (optional)">
            <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <ConfirmButton
              label="Approve"
              confirmLabel="Yes, close this account"
              loading={decide.isPending}
              onConfirm={() => decide.mutate("approve")}
            />
            <Button variant="secondary" loading={decide.isPending} onClick={() => decide.mutate("reject")}>
              Reject
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export default function Deletions() {
  const [status, setStatus] = useState("PENDING");
  const query = new URLSearchParams({ pageSize: "50", ...(status ? { status } : {}) });
  const requests = useQuery({
    queryKey: ["admin", "deletions", status],
    queryFn: () => api<Page<Item>>(`/api/admin/deletion-requests?${query}`),
  });

  return (
    <div className="max-w-3xl">
      <PageHeader title="Account closing requests" subtitle="Customers who asked us to close their account." />
      <div className="mb-4 max-w-xs">
        <Field label="Show">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="PENDING">Waiting</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="">All</option>
          </Select>
        </Field>
      </div>
      {requests.isPending && <Loading />}
      {requests.error && <Alert>{errorMessage(requests.error)}</Alert>}
      {requests.data && requests.data.items.length === 0 && <Empty>No requests here.</Empty>}
      <ul className="space-y-3">
        {requests.data?.items.map((item) => (
          <li key={item.id}>
            <Request item={item} />
          </li>
        ))}
      </ul>
    </div>
  );
}
