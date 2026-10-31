import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Alert, Card, Loading, PageHeader } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";

interface Stats {
  tags: { total: number; notActive: number; active: number; turnedOff: number; retired: number };
  stock: { IN_STOCK: number; RESERVED: number; SOLD: number; DAMAGED: number; REPLACED: number };
  users: number;
  newUsers7d: number;
  batches: number;
  scans24h: number;
  scans7d: number;
  pendingDeletions: number;
}

function Stat({ label, value, hint, to }: { label: string; value: number; hint?: string; to?: string }) {
  const body = (
    <Card className={to ? "hover:bg-subtle" : undefined}>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-3xl font-bold tabular-nums">{value.toLocaleString()}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </Card>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

export default function Overview() {
  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: () => api<Stats>("/api/admin/stats") });

  return (
    <div>
      <PageHeader title="Overview" />
      {stats.isPending && <Loading />}
      {stats.error && <Alert>{errorMessage(stats.error)}</Alert>}
      {stats.data && (
        <div className="space-y-6">
          {stats.data.pendingDeletions > 0 && (
            <Alert tone="warn">
              {stats.data.pendingDeletions} account closing request(s) waiting.{" "}
              <Link to="/admin/deletions" className="font-semibold underline">
                Review
              </Link>
            </Alert>
          )}

          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">Tags by state</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Stat label="Tags in total" value={stats.data.tags.total} to="/admin/tags" />
              <Stat label="Not active" value={stats.data.tags.notActive} to="/admin/tags?status=NOT_ACTIVE" />
              <Stat label="Active" value={stats.data.tags.active} to="/admin/tags?status=ACTIVE" />
              <Stat label="Turned off" value={stats.data.tags.turnedOff} to="/admin/tags?status=TURNED_OFF" />
              <Stat label="Retired" value={stats.data.tags.retired} to="/admin/tags?status=RETIRED" />
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">Stock</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Stat label="In stock" value={stats.data.stock.IN_STOCK} to="/admin/tags?stock=IN_STOCK" />
              <Stat label="Reserved" value={stats.data.stock.RESERVED} to="/admin/tags?stock=RESERVED" />
              <Stat label="Sold" value={stats.data.stock.SOLD} to="/admin/tags?stock=SOLD" />
              <Stat label="Damaged" value={stats.data.stock.DAMAGED} to="/admin/tags?stock=DAMAGED" />
              <Stat label="Replaced" value={stats.data.stock.REPLACED} to="/admin/tags?stock=REPLACED" />
            </div>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Customers" value={stats.data.users} hint={`${stats.data.newUsers7d} new this week`} to="/admin/users" />
            <Stat label="Batches" value={stats.data.batches} to="/admin/batches" />
            <Stat label="Scans, last 24 hours" value={stats.data.scans24h} to="/admin/activity" />
            <Stat label="Scans, last 7 days" value={stats.data.scans7d} />
          </section>
        </div>
      )}
    </div>
  );
}
