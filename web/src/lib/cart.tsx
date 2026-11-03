import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/** The basket lives in the browser. The server prices every order again, so nothing here is trusted. */
const STORAGE_KEY = "cartag.basket";

type Lines = Record<string, number>;

interface CartValue {
  lines: Lines;
  count: number;
  add: (sku: string, quantity?: number) => void;
  setQuantity: (sku: string, quantity: number) => void;
  remove: (sku: string) => void;
  clear: () => void;
}

const CartContext = createContext<CartValue | null>(null);

function load(): Lines {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : {};
    if (!parsed || typeof parsed !== "object") return {};
    const clean: Lines = {};
    for (const [sku, quantity] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof quantity === "number" && Number.isInteger(quantity) && quantity >= 1 && quantity <= 20) clean[sku] = quantity;
    }
    return clean;
  } catch {
    return {};
  }
}

/**
 * `deferLoad` starts with an empty basket and reads the saved one after the first render. A pre-rendered
 * page needs that, because its HTML was made without a basket and the first render must match it.
 */
export function CartProvider({ children, deferLoad = false }: { children: ReactNode; deferLoad?: boolean }) {
  const [lines, setLines] = useState<Lines>(() => (deferLoad ? {} : load()));
  const [loaded, setLoaded] = useState(!deferLoad);

  useEffect(() => {
    if (loaded) return;
    setLines(load());
    setLoaded(true);
  }, [loaded]);

  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch {
      // Private browsing or full storage: the basket still works until the page is closed.
    }
  }, [lines, loaded]);

  const add = useCallback((sku: string, quantity = 1) => {
    setLines((current) => ({ ...current, [sku]: Math.min(20, (current[sku] ?? 0) + quantity) }));
  }, []);
  const setQuantity = useCallback((sku: string, quantity: number) => {
    setLines((current) => {
      const next = { ...current };
      if (quantity <= 0) delete next[sku];
      else next[sku] = Math.min(20, quantity);
      return next;
    });
  }, []);
  const remove = useCallback((sku: string) => {
    setLines((current) => {
      const next = { ...current };
      delete next[sku];
      return next;
    });
  }, []);
  const clear = useCallback(() => setLines({}), []);

  const value = useMemo<CartValue>(
    () => ({ lines, count: Object.values(lines).reduce((a, b) => a + b, 0), add, setQuantity, remove, clear }),
    [lines, add, setQuantity, remove, clear],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const value = useContext(CartContext);
  if (!value) throw new Error("useCart must be used inside CartProvider");
  return value;
}
