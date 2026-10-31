import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { COLOUR_LABEL, COLOUR_SWATCH, SIZE_LABEL } from "../../components/orderBits";
import { Alert, Badge, Button, Input, Loading, PageHeader } from "../../components/ui";
import { api, errorMessage, type Product } from "../../lib/api";
import { rs } from "../../lib/format";

function Row({ product }: { product: Product }) {
  const queryClient = useQueryClient();
  const [price, setPrice] = useState(String(product.price));

  const save = useMutation({
    mutationFn: (body: { price?: number; active?: boolean }) => api(`/api/admin/products/${product.sku}`, { method: "PATCH", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "products"] }),
  });
  const changed = price !== String(product.price);

  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-4 py-3">
        <span className="flex items-center gap-3">
          <span aria-hidden="true" className="size-5 shrink-0 rounded-full border border-line" style={{ background: COLOUR_SWATCH[product.colour] }} />
          <span>
            <span className="font-medium">
              {SIZE_LABEL[product.size]}, {COLOUR_LABEL[product.colour]}
            </span>
            {product.premium && (
              <>
                {" "}
                <Badge tone="brand">Premium</Badge>
              </>
            )}
            <span className="block font-mono text-xs text-muted">{product.sku}</span>
          </span>
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-muted">Rs</span>
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            max={1_000_000}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            aria-label={`Price of ${product.name}`}
            className="w-28"
          />
          <Button variant="secondary" disabled={!changed || price === ""} loading={save.isPending} onClick={() => save.mutate({ price: Number(price) })}>
            Save
          </Button>
        </div>
        {save.error && <p className="mt-1 text-sm text-danger">{errorMessage(save.error)}</p>}
      </td>
      <td className="px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-5 accent-[var(--c-brand)]"
            checked={product.active}
            disabled={save.isPending}
            onChange={(e) => save.mutate({ active: e.target.checked })}
          />
          {product.active ? "For sale" : "Hidden"}
        </label>
      </td>
    </tr>
  );
}

export default function AdminProducts() {
  const products = useQuery({
    queryKey: ["admin", "products"],
    queryFn: async () => (await api<{ products: Product[] }>("/api/admin/products")).products,
  });

  return (
    <div>
      <PageHeader title="Products and prices" subtitle="The twelve sizes and colours the shop sells." />
      <Alert tone="warn">
        These prices are placeholders from the scope document ({rs(800)} to {rs(1100)}). Set the real prices before launch. A price change
        applies to new orders only, never to orders already placed.
      </Alert>
      <div className="mt-4">
        {products.isPending && <Loading />}
        {products.error && <Alert>{errorMessage(products.error)}</Alert>}
        {products.data && (
          <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
            <table className="w-full min-w-[38rem] text-left text-sm">
              <thead className="border-b border-line text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Product</th>
                  <th className="px-4 py-3 font-medium">Price</th>
                  <th className="px-4 py-3 font-medium">Shop</th>
                </tr>
              </thead>
              <tbody>
                {products.data.map((product) => (
                  <Row key={`${product.sku}-${product.price}-${product.active}`} product={product} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
