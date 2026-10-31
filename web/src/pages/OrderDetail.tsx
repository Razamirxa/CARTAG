import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router";
import { DELIVERY_STATUS_LABEL, OrderStatusBadge, PaymentBadge } from "../components/orderBits";
import { Alert, Button, Card, ConfirmButton, Loading, PageHeader } from "../components/ui";
import { ApiError, api, errorMessage, type Order } from "../lib/api";
import { formatDateTime, formatPkMobile, rs } from "../lib/format";

export default function OrderDetail() {
  const number = Number(useParams().number);
  const location = useLocation();
  const queryClient = useQueryClient();
  const key = ["orders", number] as const;
  const justPlaced = Boolean((location.state as { justPlaced?: boolean } | null)?.justPlaced);

  const order = useQuery({
    queryKey: key,
    queryFn: async () => (await api<{ order: Order }>(`/api/shop/orders/${number}`)).order,
  });

  const cancel = useMutation({
    mutationFn: () => api<{ order: Order }>(`/api/shop/orders/${number}/cancel`, { method: "POST", body: {} }),
    onSuccess: async ({ order: next }) => {
      queryClient.setQueryData(key, next);
      await queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  const pay = useMutation({
    mutationFn: () => api<{ checkoutUrl: string }>(`/api/shop/orders/${number}/pay`, { method: "POST", body: {} }),
    onSuccess: ({ checkoutUrl }) => window.location.assign(checkoutUrl),
  });

  if (order.isPending) return <Loading />;
  if (order.error) {
    const notFound = order.error instanceof ApiError && order.error.status === 404;
    return <Alert>{notFound ? "We could not find that order." : errorMessage(order.error)}</Alert>;
  }
  const current = order.data;
  const canPay = current.paymentMethod === "PREPAID" && current.status === "PLACED" && ["DUE", "FAILED"].includes(current.paymentStatus);
  const canCancel = current.status === "PLACED" && !["PAID", "CHECKING"].includes(current.paymentStatus);

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <Link to="/orders" className="text-sm font-medium text-brand">
        ← My orders
      </Link>
      <PageHeader
        title={current.label}
        subtitle={`Placed ${formatDateTime(current.createdAt)}`}
        actions={
          <span className="flex gap-2">
            <OrderStatusBadge status={current.status} />
            <PaymentBadge status={current.paymentStatus} />
          </span>
        }
      />

      {justPlaced && <Alert tone="success">Thank you. We have your order and will prepare it soon.</Alert>}
      {current.paymentStatus === "PAID" && current.status !== "CANCELLED" && <Alert tone="success">Your payment went through.</Alert>}
      {current.paymentStatus === "FAILED" && <Alert tone="warn">The payment did not go through. You can try again.</Alert>}
      {current.status === "CANCELLED" && current.paymentStatus === "PAID" && (
        <Alert tone="warn">This order was cancelled after it was paid. We will refund you. Please contact us if you have questions.</Alert>
      )}
      {(cancel.error || pay.error) && <Alert>{errorMessage(cancel.error ?? pay.error)}</Alert>}

      <Card>
        <h2 className="mb-2 font-semibold">Items</h2>
        <ul className="divide-y divide-line text-sm">
          {current.items?.map((item) => (
            <li key={item.sku} className="flex justify-between gap-3 py-2">
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
            <dd className="tabular-nums">{rs(current.shippingFee)}</dd>
          </div>
          <div className="flex justify-between text-base font-bold">
            <dt>Total</dt>
            <dd className="tabular-nums">{rs(current.total)}</dd>
          </div>
        </dl>
        <p className="mt-2 text-sm text-muted">
          {current.paymentMethod === "COD" ? "Pay the courier when it arrives." : "Paid online."}
        </p>
      </Card>

      <Card>
        <h2 className="mb-2 font-semibold">Delivery</h2>
        <p className="text-sm">
          {current.recipient.name} · {formatPkMobile(current.recipient.phone)}
          <br />
          {current.recipient.address}, {current.recipient.city}
        </p>
        <dl className="mt-3 space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Status</dt>
            <dd>{DELIVERY_STATUS_LABEL[current.delivery.status]}</dd>
          </div>
          {current.delivery.courier && (
            <div className="flex justify-between">
              <dt className="text-muted">Courier</dt>
              <dd>{current.delivery.courier}</dd>
            </div>
          )}
          {current.delivery.trackingNumber && (
            <div className="flex justify-between">
              <dt className="text-muted">Tracking number</dt>
              <dd className="font-mono">{current.delivery.trackingNumber}</dd>
            </div>
          )}
        </dl>
      </Card>

      {(canPay || canCancel) && (
        <div className="flex flex-wrap gap-3">
          {canPay && (
            <Button loading={pay.isPending} onClick={() => pay.mutate()}>
              Pay now
            </Button>
          )}
          {canCancel && (
            <ConfirmButton label="Cancel order" confirmLabel="Yes, cancel it" loading={cancel.isPending} onConfirm={() => cancel.mutate()} />
          )}
        </div>
      )}
    </div>
  );
}
