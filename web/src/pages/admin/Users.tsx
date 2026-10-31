import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, ConfirmButton, Empty, Field, Input, Loading, PageHeader, Pagination } from "../../components/ui";
import { api, errorMessage, type Page } from "../../lib/api";
import { formatDate, formatDateTime, formatPkMobile } from "../../lib/format";

interface UserRow {
  id: string;
  name: string;
  phone: string | null;
  phoneVerified: boolean;
  status: "ACTIVE" | "BLOCKED" | "DELETED";
  createdAt: string;
  lastLoginAt: string | null;
  tagCount: number;
}

export default function Users() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const query = new URLSearchParams({ page: String(page), pageSize: "25", ...(q ? { q } : {}) });
  const users = useQuery({
    queryKey: ["admin", "users", query.toString()],
    queryFn: () => api<Page<UserRow>>(`/api/admin/users?${query}`),
    placeholderData: (previous) => previous,
  });

  const setStatus = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "block" | "unblock" }) =>
      api(`/api/admin/users/${id}/${action}`, { method: "POST", body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  return (
    <div>
      <PageHeader title="Customers" subtitle="People who registered with a mobile number." />
      <div className="mb-4 max-w-md">
        <Field label="Search">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or mobile number" />
        </Field>
      </div>

      {setStatus.error && (
        <div className="mb-4">
          <Alert>{errorMessage(setStatus.error)}</Alert>
        </div>
      )}
      {users.isPending && <Loading />}
      {users.error && <Alert>{errorMessage(users.error)}</Alert>}
      {users.data && users.data.items.length === 0 && <Empty>No customers found.</Empty>}

      {users.data && users.data.items.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Mobile</th>
                <th className="px-4 py-3 font-medium">Tags</th>
                <th className="px-4 py-3 font-medium">Joined</th>
                <th className="px-4 py-3 font-medium">Last login</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((user) => (
                <tr key={user.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-medium">
                    {user.name}{" "}
                    {user.status === "BLOCKED" && <Badge tone="danger">Blocked</Badge>}
                    {user.status === "DELETED" && <Badge tone="neutral">Closed</Badge>}
                  </td>
                  <td className="px-4 py-3">
                    {user.phone ? formatPkMobile(user.phone) : "—"}{" "}
                    {user.phone && !user.phoneVerified && <Badge tone="warn">Not confirmed</Badge>}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{user.tagCount}</td>
                  <td className="px-4 py-3">{formatDate(user.createdAt)}</td>
                  <td className="px-4 py-3">{formatDateTime(user.lastLoginAt)}</td>
                  <td className="px-4 py-3 text-end">
                    {user.status === "ACTIVE" && (
                      <ConfirmButton
                        label="Block"
                        confirmLabel="Yes, block"
                        loading={setStatus.isPending}
                        onConfirm={() => setStatus.mutate({ id: user.id, action: "block" })}
                      />
                    )}
                    {user.status === "BLOCKED" && (
                      <Button variant="secondary" loading={setStatus.isPending} onClick={() => setStatus.mutate({ id: user.id, action: "unblock" })}>
                        Unblock
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {users.data && <Pagination page={users.data.page} pageSize={users.data.pageSize} total={users.data.total} onChange={setPage} />}
    </div>
  );
}
