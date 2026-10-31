import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import {
  ContactCardFields,
  cardFromApi,
  cardPayload,
  emptyCard,
  type CardFormValues,
} from "../components/ContactCardForm";
import { Alert, Button, Card, Loading, PageHeader } from "../components/ui";
import { ApiError, api, errorMessage, type ContactCard } from "../lib/api";
import { ME_KEY, useMe } from "../lib/auth";
import { MY_CARD_KEY } from "./Account";

export default function CardPage() {
  const me = useMe();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<CardFormValues | null>(null);
  const [saved, setSaved] = useState(false);

  const card = useQuery({
    queryKey: MY_CARD_KEY,
    queryFn: async () => (await api<{ card: ContactCard | null }>("/api/me/card")).card,
  });

  useEffect(() => {
    if (values === null && card.data !== undefined && me.data) {
      setValues(card.data ? cardFromApi(card.data) : emptyCard(me.data.name));
    }
  }, [card.data, me.data, values]);

  const save = useMutation({
    mutationFn: () => api<{ card: ContactCard }>("/api/me/card", { method: "PUT", body: cardPayload(values!) }),
    onSuccess: async ({ card: next }) => {
      setSaved(true);
      setValues(cardFromApi(next));
      queryClient.setQueryData(MY_CARD_KEY, next);
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });

  if (card.isPending || values === null) return card.error ? <Alert>{errorMessage(card.error)}</Alert> : <Loading />;

  const issues = save.error instanceof ApiError ? save.error.issues : [];
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    save.mutate();
  };

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <Link to="/account" className="text-sm font-medium text-brand">
        ← My account
      </Link>
      <PageHeader title="Contact Card" subtitle="This is what people see when they scan any of your tags." />
      {saved && <Alert tone="success">Saved. Your scan pages are updated.</Alert>}
      {!card.data && (
        <Alert tone="warn">You have not made a contact card yet. It is created when you turn on your first tag.</Alert>
      )}
      <form onSubmit={submit} className="space-y-4" noValidate>
        {save.error && issues.length === 0 && <Alert>{errorMessage(save.error)}</Alert>}
        <Card>
          <ContactCardFields values={values} onChange={setValues} issues={issues} />
        </Card>
        <Button type="submit" className="w-full" loading={save.isPending}>
          Save
        </Button>
      </form>
    </div>
  );
}
