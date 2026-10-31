import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmButton,
  Field,
  Input,
  Loading,
  PageHeader,
  StatusBadge,
  StockBadge,
} from "../../components/ui";
import { api, errorMessage, type AdminTag } from "../../lib/api";
import { formatDateTime, formatPkMobile } from "../../lib/format";
import { normalizeTagCode } from "../../lib/rules";

interface Detail {
  tag: AdminTag;
  scanCount: number;
  recentScans: Array<{ id: string; at: string; outcome: string }>;
  history: Array<{ id: string; at: string; actorType: string; action: string; meta: unknown }>;
}

const OUTCOME: Record<string, string> = {
  ACTIVE_PAGE: "Showed contact buttons",
  NOT_ACTIVE_PAGE: "Showed “not active yet”",
  TURNED_OFF_PAGE: "Showed “turned off”",
  RETIRED_PAGE: "Showed “retired”",
  NOT_FOUND: "Not found",
};

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-t border-line py-2 first:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-end font-medium">{children}</dd>
    </div>
  );
}

export default function AdminTagDetail() {
  const code = normalizeTagCode(useParams().code ?? "");
  const queryClient = useQueryClient();
  const key = ["admin", "tag", code] as const;
  const [reason, setReason] = useState("");

  const detail = useQuery({ queryKey: key, queryFn: () => api<Detail>(`/api/admin/tags/${code}`) });

  const run = useMutation({
    mutationFn: ({ action, body }: { action: string; body?: unknown }) =>
      api<{ tag: AdminTag }>(`/api/admin/tags/${code}/${action}`, { method: "POST", body: body ?? {} }),
    onSuccess: async () => {
      setReason("");
      await queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });

  if (detail.isPending) return <Loading />;
  if (detail.error) return <Alert>{errorMessage(detail.error)}</Alert>;

  const { tag, scanCount, recentScans, history } = detail.data;
  const retired = tag.status === "RETIRED";
  const canSell = !retired && (tag.stockStatus === "IN_STOCK" || tag.stockStatus === "RESERVED");

  return (
    <div className="max-w-3xl space-y-5">
      <Link to="/admin/tags" className="text-sm font-medium text-brand">
        ← Tags
      </Link>
      <PageHeader
        title={`Tag ${tag.serial}`}
        subtitle={tag.code}
        actions={
          <span className="flex gap-2">
            <StatusBadge status={tag.status} />
            <StockBadge stock={tag.stockStatus} />
          </span>
        }
      />
      {run.error && <Alert>{errorMessage(run.error)}</Alert>}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="mb-2 font-semibold">Tag</h2>
          <dl className="text-sm">
            <Row label="Batch">{tag.batch.name}</Row>
            <Row label="Created">{formatDateTime(tag.createdAt)}</Row>
            <Row label="Turned on">{formatDateTime(tag.activatedAt)}</Row>
            {retired && <Row label="Retired">{formatDateTime(tag.retiredAt)}</Row>}
            <Row label="Scans">{scanCount.toLocaleString()}</Row>
          </dl>
        </Card>
        <Card>
          <h2 className="mb-2 font-semibold">Owner</h2>
          <dl className="text-sm">
            <Row label="Name">{tag.owner?.name ?? "—"}</Row>
            <Row label="Mobile">{tag.owner ? formatPkMobile(tag.owner.phone) : "—"}</Row>
          </dl>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">Actions</h2>
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={`/t/${tag.code}`}
            target="_blank"
            rel="noopener"
            className="inline-flex min-h-11 items-center rounded-xl border border-line px-4 text-sm font-semibold hover:bg-subtle"
          >
            Open scan page
          </a>
          {canSell && (
            <Button loading={run.isPending} onClick={() => run.mutate({ action: "mark-sold" })}>
              Mark as sold
            </Button>
          )}
        </div>
        {canSell && (
          <p className="mt-2 text-sm text-muted">A customer can only turn a tag on after it is marked as sold.</p>
        )}

        {!retired && (
          <div className="mt-5 border-t border-line pt-4">
            <h3 className="font-medium">Retire this tag</h3>
            <p className="mt-1 text-sm text-muted">
              Stops the tag for good. It can never be turned on again and its code is never given to another tag. For a replacement, use a
              new tag.
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <div className="min-w-56 flex-1">
                <Field label="Reason (optional)">
                  <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} placeholder="For example damaged or lost" />
                </Field>
              </div>
              <ConfirmButton
                label="Retire tag"
                confirmLabel="Yes, retire for good"
                loading={run.isPending}
                onConfirm={() => run.mutate({ action: "retire", body: { reason } })}
              />
            </div>
          </div>
        )}
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="mb-2 font-semibold">History</h2>
          {history.length === 0 && <p className="text-sm text-muted">Nothing yet.</p>}
          <ul className="space-y-2 text-sm">
            {history.map((h) => (
              <li key={h.id} className="flex justify-between gap-3">
                <span>
                  <Badge tone={h.actorType === "ADMIN" ? "warn" : "neutral"}>{h.actorType.toLowerCase()}</Badge> {h.action}
                </span>
                <span className="shrink-0 text-muted">{formatDateTime(h.at)}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h2 className="mb-2 font-semibold">Recent scans</h2>
          {recentScans.length === 0 && <p className="text-sm text-muted">Never scanned.</p>}
          <ul className="space-y-2 text-sm">
            {recentScans.map((s) => (
              <li key={s.id} className="flex justify-between gap-3">
                <span>{OUTCOME[s.outcome] ?? s.outcome}</span>
                <span className="shrink-0 text-muted">{formatDateTime(s.at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
