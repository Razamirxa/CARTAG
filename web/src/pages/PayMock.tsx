import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router";
import { Alert, Button, Card, Loading, PageHeader } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { rs } from "../lib/format";

/**
 * A pretend payment page, used while no real payment provider is connected.
 * It does not move money. It tells the server "paid" or "failed" the same way a real provider would.
 */
export default function PayMock() {
  const id = useParams().id ?? "";
  const navigate = useNavigate();

  const payment = useQuery({
    queryKey: ["mock-payment", id],
    queryFn: () => api<{ orderNumber: number; amount: number; status: string }>(`/api/payments/mock/${id}`),
  });

  const finish = useMutation({
    mutationFn: (outcome: "success" | "failure") =>
      api(`/api/payments/mock/${id}/complete`, { method: "POST", body: { outcome } }),
    onSuccess: () => navigate(`/orders/${payment.data?.orderNumber}`, { replace: true }),
  });

  if (payment.isPending) return <Loading />;
  if (payment.error) return <Alert>{errorMessage(payment.error)}</Alert>;

  return (
    <div className="mx-auto max-w-md space-y-5">
      <PageHeader title="Test payment" />
      <Alert tone="warn">
        This is a pretend payment page for testing. No money is taken. A real payment provider will replace it.
      </Alert>
      <Card>
        <p className="text-sm text-muted">Order {payment.data.orderNumber}</p>
        <p className="mt-1 text-3xl font-bold tabular-nums">{rs(payment.data.amount)}</p>
        {finish.error && (
          <div className="mt-3">
            <Alert>{errorMessage(finish.error)}</Alert>
          </div>
        )}
        <div className="mt-5 flex flex-wrap gap-3">
          <Button loading={finish.isPending} disabled={payment.data.status !== "INITIATED"} onClick={() => finish.mutate("success")}>
            Pay now
          </Button>
          <Button variant="secondary" disabled={finish.isPending || payment.data.status !== "INITIATED"} onClick={() => finish.mutate("failure")}>
            Make it fail
          </Button>
        </div>
        {payment.data.status !== "INITIATED" && <p className="mt-3 text-sm text-muted">This payment is already {payment.data.status.toLowerCase()}.</p>}
      </Card>
    </div>
  );
}
