import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { ORDER_STATUS_LABEL, OrderStatusBadge, PAYMENT_STATUS_LABEL, PaymentBadge } from "../../components/orderBits";
import { Alert, Empty, Field, Input, Loading, PageHeader, Pagination, Select } from "../../components/ui";
import { api, errorMessage, type AdminOrder, type Page } from "../../lib/api";
import { formatDateTime, formatPkMobile, rs } from "../../lib/format";

export default function AdminOrders() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const payment = params.get("payment") ?? "";
  const method = params.get("method") ?? "";
  const q = params.get("q") ?? "";
  const page = Number(params.get("page") ?? "1") || 1;

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
  if (payment) query.set("payment", payment);
  if (method) query.set("method", method);
  if (q) query.set("q", q);

  const orders = useQuery({
    queryKey: ["admin", "orders", query.toString()],
    queryFn: () => api<Page<AdminOrder>>(`/api/admin/orders?${query}`),
    placeholderData: (previous) => previous,
  });

  return (
    <div>
      <PageHeader title="Orders" />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Search">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Order no., name, mobile, tracking" />
        </Field>
        <Field label="Order state">
          <Select value={status} onChange={(e) => update({ status: e.target.value, page: "1" })}>
            <option value="">All</option>
            {Object.entries(ORDER_STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Payment">
          <Select value={payment} onChange={(e) => update({ payment: e.target.value, page: "1" })}>
            <option value="">All</option>
            {Object.entries(PAYMENT_STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Method">
          <Select value={method} onChange={(e) => update({ method: e.target.value, page: "1" })}>
            <option value="">All</option>
            <option value="COD">Cash on delivery</option>
            <option value="PREPAID">Prepaid</option>
          </Select>
        </Field>
      </div>

      {orders.isPending && <Loading />}
      {orders.error && <Alert>{errorMessage(orders.error)}</Alert>}
      {orders.data && orders.data.items.length === 0 && <Empty>No orders match.</Empty>}

      {orders.data && orders.data.items.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[46rem] text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Order</th>
                <th className="px-4 py-3 font-medium">Placed</th>
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Payment</th>
                <th className="px-4 py-3 font-medium">State</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.items.map((order) => (
                <tr key={order.number} className="border-b border-line last:border-0 hover:bg-subtle">
                  <td className="px-4 py-3">
                    <Link to={`/admin/orders/${order.number}`} className="font-medium text-brand">
                      {order.label}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{formatDateTime(order.createdAt)}</td>
                  <td className="px-4 py-3">
                    {order.customer.name}
                    <span className="block text-xs text-muted">{formatPkMobile(order.customer.phone)}</span>
                  </td>
                  <td className="px-4 py-3 tabular-nums">{rs(order.total)}</td>
                  <td className="px-4 py-3">
                    <PaymentBadge status={order.paymentStatus} />
                  </td>
                  <td className="px-4 py-3">
                    <OrderStatusBadge status={order.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {orders.data && (
        <Pagination page={orders.data.page} pageSize={orders.data.pageSize} total={orders.data.total} onChange={(p) => update({ page: String(p) })} />
      )}
    </div>
  );
}
