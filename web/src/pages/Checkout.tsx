import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { PhoneInput } from "../components/authBits";
import { Alert, Button, Card, Field, Input, Loading, PageHeader, Textarea } from "../components/ui";
import { ApiError, api, errorMessage, type Order, type PaymentMethod } from "../lib/api";
import { useCart } from "../lib/cart";
import { useMe } from "../lib/auth";
import { formatPkMobile, rs } from "../lib/format";
import { useProducts, useShopConfig } from "./Cart";

export default function Checkout() {
  const cart = useCart();
  const me = useMe();
  const products = useProducts();
  const config = useShopConfig();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState(me.data?.name ?? "");
  const [phone, setPhone] = useState(me.data ? formatPkMobile(me.data.phone) : "");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [notes, setNotes] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("COD");

  const place = useMutation({
    mutationFn: () =>
      api<{ order: Order; checkoutUrl: string | null }>("/api/shop/orders", {
        method: "POST",
        body: {
          items: Object.entries(cart.lines).map(([sku, quantity]) => ({ sku, quantity })),
          paymentMethod: method,
          recipientName: name,
          recipientPhone: phone,
          address,
          city,
          notes,
        },
      }),
    onSuccess: async ({ order, checkoutUrl }) => {
      cart.clear();
      await queryClient.invalidateQueries({ queryKey: ["orders"] });
      if (checkoutUrl) window.location.assign(checkoutUrl);
      else navigate(`/orders/${order.number}`, { replace: true, state: { justPlaced: true } });
    },
  });

  if (products.isPending || config.isPending) return <Loading />;
  const bySku = new Map(products.data?.map((p) => [p.sku, p]) ?? []);
  const lines = Object.entries(cart.lines).filter(([sku]) => bySku.has(sku));
  if (lines.length === 0 && !place.isSuccess) return <Navigate to="/cart" replace />;

  const subtotal = lines.reduce((sum, [sku, qty]) => sum + bySku.get(sku)!.price * qty, 0);
  const shipping = config.data?.shippingFee ?? 0;
  const issues = place.error instanceof ApiError ? place.error.issues : [];
  const fieldError = (field: string) => issues.find((i) => i.field === field)?.message;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    place.mutate();
  };

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="Checkout" />
      <form onSubmit={submit} className="space-y-5" noValidate>
        {place.error && issues.length === 0 && <Alert>{errorMessage(place.error)}</Alert>}

        <Card>
          <h2 className="mb-4 font-semibold">Delivery details</h2>
          <div className="space-y-4">
            <Field label="Name of the person receiving it" error={fieldError("recipientName")}>
              <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} required />
            </Field>
            <PhoneInput value={phone} onChange={setPhone} error={fieldError("recipientPhone")} />
            <Field label="Address" error={fieldError("address")}>
              <Textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                autoComplete="street-address"
                maxLength={300}
                className="min-h-24 font-sans"
                required
              />
            </Field>
            <Field label="City" error={fieldError("city")}>
              <Input value={city} onChange={(e) => setCity(e.target.value)} autoComplete="address-level2" maxLength={60} required />
            </Field>
            <Field label="Note for the courier (optional)" error={fieldError("notes")}>
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={300} />
            </Field>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">How would you like to pay?</h2>
          <fieldset className="space-y-2">
            <legend className="sr-only">Payment method</legend>
            <label className="flex items-start gap-3 rounded-xl border border-line p-3">
              <input type="radio" name="method" className="mt-1" checked={method === "COD"} onChange={() => setMethod("COD")} />
              <span>
                <span className="block font-medium">Cash on delivery</span>
                <span className="block text-sm text-muted">Pay the courier when the tag arrives.</span>
              </span>
            </label>
            <label className={`flex items-start gap-3 rounded-xl border border-line p-3 ${config.data?.paymentEnabled ? "" : "opacity-60"}`}>
              <input
                type="radio"
                name="method"
                className="mt-1"
                checked={method === "PREPAID"}
                disabled={!config.data?.paymentEnabled}
                onChange={() => setMethod("PREPAID")}
              />
              <span>
                <span className="block font-medium">Pay online</span>
                <span className="block text-sm text-muted">
                  {config.data?.paymentEnabled
                    ? "You pay now and the order is confirmed as soon as the payment goes through."
                    : "Not available yet."}
                </span>
              </span>
            </label>
          </fieldset>
        </Card>

        <Card>
          <ul className="space-y-1 text-sm">
            {lines.map(([sku, qty]) => (
              <li key={sku} className="flex justify-between gap-3">
                <span>
                  {qty} × {bySku.get(sku)!.name}
                </span>
                <span className="tabular-nums">{rs(bySku.get(sku)!.price * qty)}</span>
              </li>
            ))}
          </ul>
          <dl className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">Delivery</dt>
              <dd className="tabular-nums">{shipping === 0 ? "To be confirmed" : rs(shipping)}</dd>
            </div>
            <div className="flex justify-between text-base font-bold">
              <dt>Total</dt>
              <dd className="tabular-nums">{rs(subtotal + shipping)}</dd>
            </div>
          </dl>
        </Card>

        <Button type="submit" className="w-full" loading={place.isPending}>
          {method === "PREPAID" ? "Place order and pay" : "Place order"}
        </Button>
        <p className="text-center text-sm text-muted">
          <Link to="/cart" className="font-medium text-brand">
            Back to basket
          </Link>
        </p>
      </form>
    </div>
  );
}
