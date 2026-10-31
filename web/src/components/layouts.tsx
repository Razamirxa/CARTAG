import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { api } from "../lib/api";
import { ADMIN_ME_KEY, ME_KEY, useAdminMe, useMe } from "../lib/auth";
import { useCart } from "../lib/cart";
import { Button, cx, linkButton } from "./ui";

/** The wordmark: a small tag with its key-ring hole, then the name set wide and heavy. */
export function Logo({ className, inverted }: { className?: string; inverted?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-2.5", className)}>
      <svg viewBox="0 0 24 30" className="h-6 w-5" aria-hidden="true">
        <rect x="1" y="1" width="22" height="28" rx="6" style={{ fill: inverted ? "currentColor" : "var(--c-brand)" }} />
        <circle cx="12" cy="7" r="2.3" style={{ fill: inverted ? "var(--c-ink-panel)" : "var(--c-bg)" }} />
        <rect x="6" y="13" width="12" height="12" rx="2" fill="#F5F1E8" />
        <path d="M8 15h3v3H8zM13 15h3v3h-3zM8 20h3v3H8zM14 21h2v2h-2z" fill="#0A0A0A" />
      </svg>
      <span className="display text-[1.15rem]">CARTAG</span>
    </span>
  );
}

const navLink = "rounded-full px-3 py-2 text-sm font-semibold hover:bg-subtle sm:px-3.5";

/** Public pages, the shop and the customer's account. */
export function SiteLayout() {
  const me = useMe();
  const cart = useCart();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const logout = useMutation({
    mutationFn: () => api("/api/auth/logout", { method: "POST", body: {} }),
    onSuccess: async () => {
      queryClient.setQueryData(ME_KEY, null);
      await queryClient.invalidateQueries();
      navigate("/");
    },
  });

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3">
          <Link to="/" aria-label="CARTAG home" className="shrink-0 rounded-lg">
            <Logo />
          </Link>
          <nav className="flex flex-wrap items-center justify-end gap-0.5 sm:gap-1">
            <Link to="/shop" className={navLink}>
              Shop
            </Link>
            {cart.count > 0 && (
              <Link to="/cart" className={cx(navLink, "bg-subtle text-brand")}>
                Basket ({cart.count})
              </Link>
            )}
            {me.data ? (
              <>
                <Link to="/account" className={navLink}>
                  My account
                </Link>
                <Button variant="secondary" loading={logout.isPending} onClick={() => logout.mutate()}>
                  Log out
                </Button>
              </>
            ) : (
              <>
                <Link to="/login" className={navLink}>
                  Log in
                </Link>
                <Link to="/register" className={linkButton("primary")}>
                  <span className="sm:hidden">Sign up</span>
                  <span className="hidden sm:inline">Create account</span>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-12">
        <Outlet />
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-muted">
          <div>
            <Logo className="text-ink" />
            <p className="mt-2">Anyone can reach you. Your number stays off the page.</p>
          </div>
          <nav className="flex flex-wrap gap-x-5 gap-y-1 font-medium">
            <Link to="/shop" className="hover:text-ink">
              Shop
            </Link>
            <Link to="/orders" className="hover:text-ink">
              My orders
            </Link>
            <Link to="/account" className="hover:text-ink">
              My tags
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

const adminLinks = [
  { to: "/admin", label: "Overview", end: true },
  { to: "/admin/orders", label: "Orders" },
  { to: "/admin/products", label: "Products" },
  { to: "/admin/batches", label: "QR batches" },
  { to: "/admin/tags", label: "Tags" },
  { to: "/admin/users", label: "Customers" },
  { to: "/admin/deletions", label: "Closing requests" },
  { to: "/admin/activity", label: "Activity" },
];

/** The team panel. It is deliberately darker than the shop, so nobody mistakes where they are. */
export function AdminLayout() {
  const me = useAdminMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const logout = useMutation({
    mutationFn: () => api("/api/admin/auth/logout", { method: "POST", body: {} }),
    onSuccess: () => {
      queryClient.setQueryData(ADMIN_ME_KEY, null);
      queryClient.clear();
      navigate("/admin/login");
    },
  });

  const signOut = (
    <button
      type="button"
      onClick={() => logout.mutate()}
      disabled={logout.isPending}
      className="min-h-11 w-full rounded-full border border-on-panel/25 px-4 text-sm font-semibold text-on-panel hover:bg-on-panel/10 disabled:opacity-60"
    >
      Log out
    </button>
  );

  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <aside className="bg-panel text-on-panel md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <div className="flex items-center justify-between px-5 py-4 md:block md:py-6">
          <Logo inverted />
          <span className="text-sm text-on-panel/60 md:mt-1 md:block">Team panel</span>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-y-auto md:pb-4">
          {adminLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                cx(
                  "whitespace-nowrap rounded-xl px-3.5 py-2.5 text-sm font-semibold",
                  isActive ? "bg-on-panel text-panel" : "text-on-panel/80 hover:bg-on-panel/10",
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden px-5 py-5 md:block">
          <p className="mb-3 truncate text-sm text-on-panel/60">{me.data?.email}</p>
          {signOut}
        </div>
      </aside>
      <main className="min-w-0 px-4 py-8 md:px-10">
        <Outlet />
        <div className="mt-10 max-w-xs md:hidden">
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="min-h-11 w-full rounded-full border border-line px-4 text-sm font-semibold hover:bg-subtle"
          >
            Log out
          </button>
        </div>
      </main>
    </div>
  );
}
