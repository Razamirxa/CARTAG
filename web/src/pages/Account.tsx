import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { Alert, Button, Card, Empty, Field, Input, Loading, PageHeader, StatusBadge } from "../components/ui";
import { api, errorMessage, type OwnerTag } from "../lib/api";
import { useMe } from "../lib/auth";
import { formatDate, formatPkMobile } from "../lib/format";
import { isValidTagCode, normalizeTagCode } from "../lib/rules";

export const MY_TAGS_KEY = ["my-tags"] as const;
export const MY_CARD_KEY = ["my-card"] as const;

/** Accepts the bare code or the whole link printed on the tag. */
function extractCode(input: string): string | null {
  const last = input.trim().split(/[/?#\s]+/).filter(Boolean).pop() ?? "";
  const code = normalizeTagCode(last);
  return isValidTagCode(code) ? code : null;
}

export default function Account() {
  const me = useMe();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const tags = useQuery({
    queryKey: MY_TAGS_KEY,
    queryFn: async () => (await api<{ tags: OwnerTag[] }>("/api/me/tags")).tags,
  });

  const add = (event: FormEvent) => {
    event.preventDefault();
    const code = extractCode(input);
    if (!code) {
      setError("That does not look like a tag code. Scan the QR on your tag, or copy the link under it.");
      return;
    }
    navigate(`/activate/${code}`);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="My CARTAG tags" subtitle={me.data ? `${me.data.name} · ${formatPkMobile(me.data.phone)}` : undefined} />

      {tags.isPending && <Loading />}
      {tags.error && <Alert>{errorMessage(tags.error)}</Alert>}
      {tags.data && tags.data.length === 0 && (
        <Empty>You have no tags yet. Scan the QR code on your CARTAG with your phone camera to turn it on, or add it below.</Empty>
      )}

      <ul className="space-y-3">
        {tags.data?.map((tag) => (
          <li key={tag.code}>
            <Link to={`/account/tags/${tag.code}`} className="block rounded-2xl border border-line bg-surface p-4 hover:bg-subtle">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-lg font-bold tracking-wider">{tag.code}</span>
                <StatusBadge status={tag.status} />
              </div>
              <p className="mt-1 text-sm text-muted">
                Tag no. {tag.serial}
                {tag.activatedAt && ` · turned on ${formatDate(tag.activatedAt)}`}
              </p>
            </Link>
          </li>
        ))}
      </ul>

      <Card>
        <h2 className="font-semibold">Add a tag</h2>
        <form onSubmit={add} className="mt-3 space-y-3" noValidate>
          <Field label="Tag code or link" error={error ?? undefined} hint="Printed under the QR code on your tag.">
            <Input
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setError(null);
              }}
              autoCapitalize="characters"
              autoComplete="off"
              placeholder="K7X9M2QP4A"
            />
          </Field>
          <Button type="submit">Continue</Button>
        </form>
      </Card>

      <Card>
        <h2 className="font-semibold">Your account</h2>
        <ul className="mt-2 divide-y divide-line text-sm">
          <li>
            <Link to="/orders" className="flex items-center justify-between py-3 font-medium hover:text-brand">
              My orders <span aria-hidden="true">›</span>
            </Link>
          </li>
          <li>
            <Link to="/account/card" className="flex items-center justify-between py-3 font-medium hover:text-brand">
              Contact Card and Emergency Mode <span aria-hidden="true">›</span>
            </Link>
          </li>
          <li>
            <Link to="/account/mobile" className="flex items-center justify-between py-3 font-medium hover:text-brand">
              Change mobile number <span aria-hidden="true">›</span>
            </Link>
          </li>
          <li>
            <Link to="/account/delete" className="flex items-center justify-between py-3 font-medium text-danger">
              Close my account <span aria-hidden="true">›</span>
            </Link>
          </li>
        </ul>
      </Card>
    </div>
  );
}
