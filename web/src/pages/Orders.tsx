import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { OrderStatusBadge, PaymentBadge } from "../components/orderBits";
import { Alert, Empty, Loading, PageHeader } from "../components/ui";
import { api, errorMessage, type Order } from "../lib/api";
import { formatDate, rs } from "../lib/format";

export default function Orders() {
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: async () => (await api<{ orders: Order[] }>("/api/shop/orders")).orders,
  });

  return (
    <div className="space-y-5">
      <PageHeader title="My orders" />
      {orders.isPending && <Loading />}
      {orders.error && <Alert>{errorMessage(orders.error)}</Alert>}
      {orders.data && orders.data.length === 0 && (
        <Empty>
          You have not ordered anything yet.{" "}
          <Link to="/shop" className="font-medium text-brand">
            Visit the shop
          </Link>
        </Empty>
      )}
      <ul className="space-y-3">
        {orders.data?.map((order) => (
          <li key={order.number}>
            <Link to={`/orders/${order.number}`} className="block rounded-2xl border border-line bg-surface p-4 hover:bg-subtle">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{order.label}</span>
                <span className="flex gap-2">
                  <OrderStatusBadge status={order.status} />
                  <PaymentBadge status={order.paymentStatus} />
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {formatDate(order.createdAt)} · {rs(order.total)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
