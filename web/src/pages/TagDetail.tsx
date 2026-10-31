import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router";
import { Alert, Button, Card, ConfirmButton, Loading, PageHeader, StatusBadge } from "../components/ui";
import { ApiError, api, errorMessage, type OwnerTag } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { normalizeTagCode } from "../lib/rules";
import { MY_TAGS_KEY } from "./Account";

export default function TagDetail() {
  const code = normalizeTagCode(useParams().code ?? "");
  const location = useLocation();
  const queryClient = useQueryClient();
  const key = ["my-tag", code] as const;
  const justActivated = Boolean((location.state as { justActivated?: boolean } | null)?.justActivated);

  const tag = useQuery({
    queryKey: key,
    queryFn: async () => (await api<{ tag: OwnerTag }>(`/api/me/tags/${code}`)).tag,
  });

  const toggle = useMutation({
    mutationFn: (action: "turn-off" | "turn-on") =>
      api<{ tag: OwnerTag }>(`/api/me/tags/${code}/${action}`, { method: "POST", body: {} }),
    onSuccess: async ({ tag: next }) => {
      queryClient.setQueryData(key, next);
      await queryClient.invalidateQueries({ queryKey: MY_TAGS_KEY });
    },
  });

  if (tag.isPending) return <Loading />;
  if (tag.error) {
    const notFound = tag.error instanceof ApiError && tag.error.status === 404;
    return <Alert>{notFound ? "We could not find that tag on your account." : errorMessage(tag.error)}</Alert>;
  }
  const current = tag.data;

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <Link to="/account" className="text-sm font-medium text-brand">
        ← My tags
      </Link>
      <PageHeader
        title={current.code}
        subtitle={`Tag no. ${current.serial}${current.activatedAt ? ` · turned on ${formatDateTime(current.activatedAt)}` : ""}`}
        actions={<StatusBadge status={current.status} />}
      />

      {justActivated && current.status === "ACTIVE" && <Alert tone="success">Your tag is on. Anyone who scans it can now reach you.</Alert>}
      {current.status === "RETIRED" && (
        <Alert tone="warn">This tag has been retired. It cannot be turned on again. Please contact us if you need a replacement.</Alert>
      )}
      {toggle.error && <Alert>{errorMessage(toggle.error)}</Alert>}

      <Card>
        <h2 className="font-semibold">What people see</h2>
        <p className="mt-1 text-sm text-muted">
          Your name, a Call Owner button and a WhatsApp Owner button. Your number is never shown as text.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href={`/t/${current.code}`}
            target="_blank"
            rel="noopener"
            className="inline-flex min-h-11 items-center rounded-xl border border-line px-4 text-sm font-semibold hover:bg-subtle"
          >
            Open my scan page
          </a>
          <Link
            to="/account/card"
            className="inline-flex min-h-11 items-center rounded-xl border border-line px-4 text-sm font-semibold hover:bg-subtle"
          >
            Edit contact card
          </Link>
        </div>
      </Card>

      {current.status !== "RETIRED" && current.status !== "NOT_ACTIVE" && (
        <Card>
          <h2 className="font-semibold">{current.status === "ACTIVE" ? "Turn this tag off" : "Turn this tag back on"}</h2>
          <p className="mt-1 text-sm text-muted">
            {current.status === "ACTIVE"
              ? "While it is off, anyone who scans it sees that it is turned off and no details about you."
              : "Anyone who scans it will see your contact buttons again."}
          </p>
          <div className="mt-3">
            {current.status === "ACTIVE" ? (
              <ConfirmButton
                label="Turn off"
                confirmLabel="Yes, turn it off"
                loading={toggle.isPending}
                onConfirm={() => toggle.mutate("turn-off")}
              />
            ) : (
              <Button loading={toggle.isPending} onClick={() => toggle.mutate("turn-on")}>
                Turn on
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
