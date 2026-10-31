import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Alert, Empty, Field, Input, Loading, PageHeader, Pagination, Select, StatusBadge, StockBadge } from "../../components/ui";
import { api, errorMessage, type AdminTag, type Page } from "../../lib/api";
import { formatPkMobile } from "../../lib/format";
import { STOCK_STATUSES, TAG_STATUSES } from "../../lib/rules";

const STATUS_NAMES: Record<string, string> = {
  NOT_ACTIVE: "Not active",
  ACTIVE: "Active",
  TURNED_OFF: "Turned off",
  RETIRED: "Retired",
};
const STOCK_NAMES: Record<string, string> = {
  IN_STOCK: "In stock",
  RESERVED: "Reserved",
  SOLD: "Sold",
  DAMAGED: "Damaged",
  REPLACED: "Replaced",
};

export default function Tags() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const stock = params.get("stock") ?? "";
  const q = params.get("q") ?? "";
  const batchId = params.get("batchId") ?? "";
  const page = Number(params.get("page") ?? "1") || 1;

  // The search box updates as you type, but the list only reloads once you pause.
  const [search, setSearch] = useState(q);
  useEffect(() => {
    if (search === q) return;
    const timer = setTimeout(() => update({ q: search, page: "1" }), 350);
    return () => clearTimeout(timer);
  }, [search]);

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  }

  const query = new URLSearchParams({ page: String(page), pageSize: "25" });
  if (status) query.set("status", status);
  if (stock) query.set("stock", stock);
  if (q) query.set("q", q);
  if (batchId) query.set("batchId", batchId);

  const tags = useQuery({
    queryKey: ["admin", "tags", query.toString()],
    queryFn: () => api<Page<AdminTag>>(`/api/admin/tags?${query}`),
    placeholderData: (previous) => previous,
  });

  return (
    <div>
      <PageHeader title="Tags" />
      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_12rem_12rem]">
        <Field label="Search">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Code, serial number, customer name or mobile" />
        </Field>
        <Field label="Tag state">
          <Select value={status} onChange={(e) => update({ status: e.target.value, page: "1" })}>
            <option value="">All</option>
            {TAG_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_NAMES[s]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Stock">
          <Select value={stock} onChange={(e) => update({ stock: e.target.value, page: "1" })}>
            <option value="">All</option>
            {STOCK_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STOCK_NAMES[s]}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {tags.isPending && <Loading />}
      {tags.error && <Alert>{errorMessage(tags.error)}</Alert>}
      {tags.data && tags.data.items.length === 0 && <Empty>No tags match.</Empty>}

      {tags.data && tags.data.items.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Code</th>
                <th className="px-4 py-3 font-medium">State</th>
                <th className="px-4 py-3 font-medium">Stock</th>
                <th className="px-4 py-3 font-medium">Owner</th>
              </tr>
            </thead>
            <tbody>
              {tags.data.items.map((tag) => (
                <tr key={tag.code} className="border-b border-line last:border-0 hover:bg-subtle">
                  <td className="px-4 py-3 tabular-nums">
                    <Link to={`/admin/tags/${tag.code}`} className="font-medium text-brand">
                      {tag.serial}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono">{tag.code}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={tag.status} />
                  </td>
                  <td className="px-4 py-3">
                    <StockBadge stock={tag.stockStatus} />
                  </td>
                  <td className="px-4 py-3">
                    {tag.owner ? (
                      <>
                        {tag.owner.name}
                        <span className="block text-xs text-muted">{formatPkMobile(tag.owner.phone)}</span>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tags.data && <Pagination page={tags.data.page} pageSize={tags.data.pageSize} total={tags.data.total} onChange={(p) => update({ page: String(p) })} />}
    </div>
  );
}
