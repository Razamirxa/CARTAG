import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Alert, Button, Card, Empty, Loading, PageHeader } from "../components/ui";
import { api, errorMessage, type Product } from "../lib/api";
import { useCart } from "../lib/cart";
import { rs } from "../lib/format";

export interface ShopConfig {
  paymentEnabled: boolean;
  shippingFee: number;
}

export function useShopConfig() {
  return useQuery({ queryKey: ["shop", "config"], queryFn: () => api<ShopConfig>("/api/shop/config") });
}

export function useProducts() {
  return useQuery({
    queryKey: ["shop", "products"],
    queryFn: async () => (await api<{ products: Product[] }>("/api/shop/products")).products,
  });
}

export default function Cart() {
  const cart = useCart();
  const products = useProducts();
  const config = useShopConfig();

  if (products.isPending || config.isPending) return <Loading />;
  if (products.error) return <Alert>{errorMessage(products.error)}</Alert>;

  const bySku = new Map(products.data.map((p) => [p.sku, p]));
  const lines = Object.entries(cart.lines).map(([sku, quantity]) => ({ sku, quantity, product: bySku.get(sku) }));
  const available = lines.filter((l) => l.product);
  const gone = lines.filter((l) => !l.product);
  const subtotal = available.reduce((sum, l) => sum + l.product!.price * l.quantity, 0);
  const shipping = config.data?.shippingFee ?? 0;

  if (lines.length === 0) {
    return (
      <div className="space-y-4">
        <PageHeader title="Your basket" />
        <Empty>Your basket is empty.</Empty>
        <Link to="/shop" className="inline-block font-medium text-brand">
          Go to the shop
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <PageHeader title="Your basket" />
      {gone.length > 0 && (
        <Alert tone="warn">
          Some items are no longer sold and were left out.{" "}
          <button type="button" className="font-semibold underline" onClick={() => gone.forEach((l) => cart.remove(l.sku))}>
            Remove them
          </button>
        </Alert>
      )}

      <Card>
        <ul className="divide-y divide-line">
          {available.map(({ sku, quantity, product }) => (
            <li key={sku} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <span>
                <span className="block font-medium">{product!.name}</span>
                <span className="text-sm text-muted">{rs(product!.price)} each</span>
              </span>
              <span className="flex items-center gap-2">
                <Button variant="secondary" aria-label={`One less ${product!.name}`} onClick={() => cart.setQuantity(sku, quantity - 1)}>
                  −
                </Button>
                <span className="w-8 text-center font-semibold tabular-nums" aria-live="polite">
                  {quantity}
                </span>
                <Button variant="secondary" aria-label={`One more ${product!.name}`} disabled={quantity >= 20} onClick={() => cart.setQuantity(sku, quantity + 1)}>
                  +
                </Button>
                <span className="w-24 text-end font-semibold tabular-nums">{rs(product!.price * quantity)}</span>
              </span>
            </li>
          ))}
        </ul>
        <dl className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Items</dt>
            <dd className="tabular-nums">{rs(subtotal)}</dd>
          </div>
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

      <div className="flex flex-wrap gap-3">
        <Link
          to="/checkout"
          className="inline-flex min-h-12 flex-1 items-center justify-center rounded-xl bg-brand px-6 font-semibold text-on-brand hover:bg-brand-hover"
        >
          Checkout
        </Link>
        <Link to="/shop" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-line px-6 font-semibold hover:bg-subtle">
          Keep shopping
        </Link>
      </div>
    </div>
  );
}
