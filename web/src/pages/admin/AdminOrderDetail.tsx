import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { DELIVERY_STATUS_LABEL, OrderStatusBadge, PaymentBadge } from "../../components/orderBits";
import { Alert, Badge, Button, Card, ConfirmButton, Field, Input, Loading, PageHeader, Select } from "../../components/ui";
import { api, errorMessage, type AdminOrder, type DeliveryStatus, type OrderStatus } from "../../lib/api";
import { formatDateTime, formatPkMobile, rs } from "../../lib/format";

interface Detail {
  order: AdminOrder;
  history: Array<{ id: string; at: string; actorType: string; action: string }>;
}

const NEXT: Partial<Record<OrderStatus, { to: OrderStatus; label: string }>> = {
  PLACED: { to: "PROCESSING", label: "Start preparing" },
  PROCESSING: { to: "SHIPPED", label: "Mark as shipped" },
  SHIPPED: { to: "DELIVERED", label: "Mark as delivered" },
};

export default function AdminOrderDetail() {
  const number = Number(useParams().number);
  const queryClient = useQueryClient();
  const key = ["admin", "order", number] as const;

  const detail = useQuery({ queryKey: key, queryFn: () => api<Detail>(`/api/admin/orders/${number}`) });

  const [courier, setCourier] = useState("");
  const [tracking, setTracking] = useState("");
  const [deliveryStatus, setDeliveryStatus] = useState<DeliveryStatus>("NOT_BOOKED");
  const loaded = detail.data?.order;
  useEffect(() => {
    if (loaded) {
      setCourier(loaded.delivery.courier ?? "");
      setTracking(loaded.delivery.trackingNumber ?? "");
      setDeliveryStatus(loaded.delivery.status);
    }
  }, [loaded?.number, loaded?.delivery.courier, loaded?.delivery.trackingNumber, loaded?.delivery.status]);

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin"] });
  };
  const changeStatus = useMutation({
    mutationFn: (status: OrderStatus) => api(`/api/admin/orders/${number}/status`, { method: "POST", body: { status } }),
    onSuccess: done,
  });
  const saveDelivery = useMutation({
    mutationFn: () =>
      api(`/api/admin/orders/${number}/delivery`, {
        method: "PATCH",
        body: { courier, trackingNumber: tracking, deliveryStatus },
      }),
    onSuccess: done,
  });
  const payment = useMutation({
    mutationFn: (action: "collected" | "refunded") => api(`/api/admin/orders/${number}/payment/${action}`, { method: "POST", body: {} }),
    onSuccess: done,
  });

  if (detail.isPending) return <Loading />;
  if (detail.error) return <Alert>{errorMessage(detail.error)}</Alert>;
  const { order, history } = detail.data;
  const next = NEXT[order.status];
  const canCancel = order.status === "PLACED" || order.status === "PROCESSING";
  const canCollect = order.paymentMethod === "COD" && order.paymentStatus === "COD_PENDING" && ["SHIPPED", "DELIVERED"].includes(order.status);
  const canRefund = order.paymentStatus === "PAID" || order.paymentStatus === "COD_COLLECTED";
  const error = changeStatus.error ?? saveDelivery.error ?? payment.error;

  const submitDelivery = (event: FormEvent) => {
    event.preventDefault();
    saveDelivery.mutate();
  };

  return (
    <div className="max-w-3xl space-y-5">
      <Link to="/admin/orders" className="text-sm font-medium text-brand">
        ← Orders
      </Link>
      <PageHeader
        title={order.label}
        subtitle={`Placed ${formatDateTime(order.createdAt)}`}
        actions={
          <span className="flex gap-2">
            <OrderStatusBadge status={order.status} />
            <PaymentBadge status={order.paymentStatus} />
          </span>
        }
      />
      {error && <Alert>{errorMessage(error)}</Alert>}
      {order.status === "CANCELLED" && order.paymentStatus === "PAID" && (
        <Alert tone="warn">This order was cancelled but the customer had paid. Refund it, then mark it refunded below.</Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="mb-2 font-semibold">Customer</h2>
          <p className="text-sm">
            {order.customer.name}
            <br />
            {order.customer.phone.startsWith("deleted:") ? "Closed account" : formatPkMobile(order.customer.phone)}
          </p>
          <h2 className="mb-2 mt-4 font-semibold">Deliver to</h2>
          <p className="text-sm">
            {order.recipient.name} · {formatPkMobile(order.recipient.phone)}
            <br />
            {order.recipient.address}, {order.recipient.city}
            {order.recipient.notes && (
              <>
                <br />
                <span className="text-muted">Note: {order.recipient.notes}</span>
              </>
            )}
          </p>
        </Card>
        <Card>
          <h2 className="mb-2 font-semibold">Items</h2>
          <ul className="space-y-1 text-sm">
            {order.items?.map((item) => (
              <li key={item.sku} className="flex justify-between gap-3">
                <span>
                  {item.quantity} × {item.name}
                </span>
                <span className="tabular-nums">{rs(item.lineTotal)}</span>
              </li>
            ))}
          </ul>
          <dl className="mt-2 space-y-1 border-t border-line pt-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">Delivery</dt>
              <dd className="tabular-nums">{rs(order.shippingFee)}</dd>
            </div>
            <div className="flex justify-between font-bold">
              <dt>Total</dt>
              <dd className="tabular-nums">{rs(order.total)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Method</dt>
              <dd>{order.paymentMethod === "COD" ? "Cash on delivery" : "Prepaid"}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">Steps</h2>
        <div className="flex flex-wrap gap-2">
          {next && (
            <Button loading={changeStatus.isPending} onClick={() => changeStatus.mutate(next.to)}>
              {next.label}
            </Button>
          )}
          {canCancel && (
            <ConfirmButton
              label="Cancel order"
              confirmLabel="Yes, cancel"
              loading={changeStatus.isPending}
              onConfirm={() => changeStatus.mutate("CANCELLED")}
            />
          )}
          {canCollect && (
            <Button variant="secondary" loading={payment.isPending} onClick={() => payment.mutate("collected")}>
              Courier collected the cash
            </Button>
          )}
          {canRefund && (
            <ConfirmButton
              label="Mark as refunded"
              confirmLabel="Yes, refunded"
              loading={payment.isPending}
              onConfirm={() => payment.mutate("refunded")}
            />
          )}
          {!next && !canCancel && !canCollect && !canRefund && <p className="text-sm text-muted">Nothing more to do on this order.</p>}
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">Courier and tracking</h2>
        <form onSubmit={submitDelivery} className="grid gap-3 sm:grid-cols-3" noValidate>
          <Field label="Courier">
            <Input value={courier} onChange={(e) => setCourier(e.target.value)} maxLength={40} placeholder="For example TCS" />
          </Field>
          <Field label="Tracking number">
            <Input value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={60} />
          </Field>
          <Field label="Delivery status">
            <Select value={deliveryStatus} onChange={(e) => setDeliveryStatus(e.target.value as DeliveryStatus)}>
              {Object.entries(DELIVERY_STATUS_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <div className="sm:col-span-3">
            <Button type="submit" variant="secondary" loading={saveDelivery.isPending}>
              Save delivery details
            </Button>
          </div>
        </form>
      </Card>

      {order.payments && order.payments.length > 0 && (
        <Card>
          <h2 className="mb-2 font-semibold">Online payment attempts</h2>
          <ul className="space-y-2 text-sm">
            {order.payments.map((p) => (
              <li key={p.id} className="flex flex-wrap justify-between gap-2">
                <span>
                  {p.provider} · {rs(p.amount)} · <Badge tone={p.status === "SUCCEEDED" ? "success" : p.status === "FAILED" ? "danger" : "neutral"}>{p.status.toLowerCase()}</Badge>
                  {p.reference && <span className="ms-2 font-mono text-xs text-muted">{p.reference}</span>}
                </span>
                <span className="text-muted">{formatDateTime(p.createdAt)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <h2 className="mb-2 font-semibold">History</h2>
        <ul className="space-y-2 text-sm">
          {history.map((h) => (
            <li key={h.id} className="flex justify-between gap-3">
              <span>
                <Badge tone={h.actorType === "ADMIN" ? "warn" : h.actorType === "SYSTEM" ? "brand" : "neutral"}>{h.actorType.toLowerCase()}</Badge> {h.action}
              </span>
              <span className="shrink-0 text-muted">{formatDateTime(h.at)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
