import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { SIZE_LABEL } from "../components/orderBits";
import { Swatch, TAG_COLOURS, TagArt } from "../components/TagArt";
import { Alert, Badge, Button, PageHeader } from "../components/ui";
import { api, errorMessage, type Product, type ProductColour, type ProductSize } from "../lib/api";
import { useCart } from "../lib/cart";
import { rs } from "../lib/format";

const SIZES: ProductSize[] = ["COMPACT", "STANDARD", "LARGE"];
const COLOURS: ProductColour[] = ["BLACK", "IVORY", "BURGUNDY", "GLACIER"];
// Drawn to show how the sizes compare to each other, not their real measurements.
const ART_WIDTH: Record<ProductSize, string> = { COMPACT: "w-28", STANDARD: "w-36", LARGE: "w-44" };

/**
 * One size. While the prices load (and in the pre-rendered page) `products` is null: the card is drawn
 * without a price and its button waits, so the page has its full text before any data arrives.
 */
function SizeCard({ size, products }: { size: ProductSize; products: Product[] | null }) {
  const cart = useCart();
  const [colour, setColour] = useState<ProductColour>("BLACK");
  const [added, setAdded] = useState(false);
  const product = products && (products.find((p) => p.colour === colour) ?? products[0]);
  if (products && !product) return null;
  const inBasket = product ? (cart.lines[product.sku] ?? 0) : 0;
  const premium = product ? product.premium : colour === "BURGUNDY" || colour === "GLACIER";

  return (
    <article className="flex flex-col rounded-[1.5rem] border border-line bg-surface p-4 sm:p-5">
      <div className="flex min-h-72 items-end justify-center rounded-[1.1rem] bg-subtle px-4 pb-6 pt-8">
        <TagArt colour={colour} title={`${SIZE_LABEL[size]} tag in ${TAG_COLOURS[colour].name}`} className={`${ART_WIDTH[size]} transition-[width] duration-300`} />
      </div>
      <div className="mt-5 flex items-baseline justify-between gap-3">
        <h2 className="heading text-2xl">{SIZE_LABEL[size]}</h2>
        {product ? (
          <p className="heading text-2xl tabular-nums">{rs(product.price)}</p>
        ) : (
          <span className="h-7 w-20 animate-pulse rounded-lg bg-subtle" aria-label="Loading the price" />
        )}
      </div>
      <p className="mt-1 min-h-6 text-sm text-muted" aria-live="polite">
        {TAG_COLOURS[colour].name}
        {premium && " is a premium colour"}
      </p>
      <div className="-ms-2 mt-1 flex gap-0.5" role="group" aria-label={`Colour of the ${SIZE_LABEL[size]} tag`}>
        {COLOURS.map((c) => (
          <Swatch key={c} colour={c} selected={c === colour} onClick={() => setColour(c)} />
        ))}
      </div>
      {product?.description && <p className="mt-3 text-sm text-muted">{product.description}</p>}
      <div className="mt-5">
        <Button
          className="w-full"
          variant={added ? "secondary" : "primary"}
          disabled={!product}
          onClick={() => {
            if (!product) return;
            cart.add(product.sku);
            setAdded(true);
            setTimeout(() => setAdded(false), 1600);
          }}
        >
          {added ? "Added to basket" : "Add to basket"}
        </Button>
        {inBasket > 0 && !added && (
          <p className="mt-2 text-center text-sm text-muted">
            {inBasket} in your basket,{" "}
            <Link to="/cart" className="font-semibold text-brand underline">
              view it
            </Link>
          </p>
        )}
      </div>
    </article>
  );
}

export default function Shop() {
  const cart = useCart();
  const products = useQuery({
    queryKey: ["shop", "products"],
    queryFn: async () => (await api<{ products: Product[] }>("/api/shop/products")).products,
  });

  return (
    <div>
      <PageHeader
        title="Choose your CARTAG"
        subtitle="Pick a size and a colour. You turn the tag on with your phone when it arrives."
        actions={
          cart.count > 0 ? (
            <Link
              to="/cart"
              className="inline-flex min-h-11 items-center rounded-full bg-brand px-5 text-sm font-semibold text-on-brand hover:bg-brand-hover"
            >
              Basket ({cart.count})
            </Link>
          ) : undefined
        }
      />
      <p className="-mt-3 mb-8 flex flex-wrap items-center gap-2 text-sm text-muted">
        <Badge tone="brand">Premium</Badge> Burgundy and Glacier cost a little more than Black and Ivory.
      </p>

      {products.error && <Alert>{errorMessage(products.error)}</Alert>}
      {products.data && products.data.length === 0 && <Alert tone="warn">The shop has no products right now. Please check back soon.</Alert>}

      <div className="grid gap-5 md:grid-cols-3">
        {!products.error &&
          SIZES.map((size) => (
            <SizeCard key={size} size={size} products={products.data ? products.data.filter((p) => p.size === size) : null} />
          ))}
      </div>
    </div>
  );
}
