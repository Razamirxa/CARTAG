import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Alert, Badge, Button, Empty, Loading, PageHeader, Pagination } from "../../components/ui";
import { api, errorMessage, type Page } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

interface AuditItem {
  id: string;
  at: string;
  actorType: string;
  action: string;
}
interface ScanItem {
  id: string;
  at: string;
  outcome: string;
  code: string;
}

const OUTCOME: Record<string, string> = {
  ACTIVE_PAGE: "Contact buttons shown",
  NOT_ACTIVE_PAGE: "Not active yet",
  TURNED_OFF_PAGE: "Turned off",
  RETIRED_PAGE: "Retired",
  NOT_FOUND: "Unknown code",
};

export default function Activity() {
  const [tab, setTab] = useState<"audit" | "scans">("audit");
  const [page, setPage] = useState(1);

  const activity = useQuery({
    queryKey: ["admin", "activity", tab, page],
    queryFn: () => api<Page<AuditItem | ScanItem>>(`/api/admin/activity?type=${tab}&page=${page}&pageSize=30`),
    placeholderData: (previous) => previous,
  });

  const switchTab = (next: "audit" | "scans") => {
    setTab(next);
    setPage(1);
  };

  return (
    <div>
      <PageHeader title="Activity" subtitle="Every change made by customers and the team, and every scan." />
      <div className="mb-4 flex gap-2">
        <Button variant={tab === "audit" ? "primary" : "secondary"} onClick={() => switchTab("audit")}>
          Changes
        </Button>
        <Button variant={tab === "scans" ? "primary" : "secondary"} onClick={() => switchTab("scans")}>
          Scans
        </Button>
      </div>

      {activity.isPending && <Loading />}
      {activity.error && <Alert>{errorMessage(activity.error)}</Alert>}
      {activity.data && activity.data.items.length === 0 && <Empty>Nothing here yet.</Empty>}

      {activity.data && activity.data.items.length > 0 && (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface text-sm">
          {tab === "audit"
            ? (activity.data.items as AuditItem[]).map((item) => (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                  <span className="flex items-center gap-2">
                    <Badge tone={item.actorType === "ADMIN" ? "warn" : item.actorType === "USER" ? "brand" : "neutral"}>
                      {item.actorType.toLowerCase()}
                    </Badge>
                    <span className="font-medium">{item.action}</span>
                  </span>
                  <span className="text-muted">{formatDateTime(item.at)}</span>
                </li>
              ))
            : (activity.data.items as ScanItem[]).map((item) => (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                  <span>
                    <Link to={`/admin/tags/${item.code}`} className="font-mono font-medium text-brand">
                      {item.code}
                    </Link>
                    <span className="ms-2">{OUTCOME[item.outcome] ?? item.outcome}</span>
                  </span>
                  <span className="text-muted">{formatDateTime(item.at)}</span>
                </li>
              ))}
        </ul>
      )}
      {activity.data && <Pagination page={activity.data.page} pageSize={activity.data.pageSize} total={activity.data.total} onChange={setPage} />}
    </div>
  );
}
