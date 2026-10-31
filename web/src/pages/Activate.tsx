import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { OtpInput, useCountdown } from "../components/authBits";
import {
  ContactCardFields,
  cardFromApi,
  cardPayload,
  emptyCard,
  type CardFormValues,
} from "../components/ContactCardForm";
import { Alert, Button, Card, Loading, PageHeader } from "../components/ui";
import { ApiError, api, errorMessage, type ContactCard, type OwnerTag, type PublicTag } from "../lib/api";
import { ME_KEY, useMe } from "../lib/auth";
import { formatPkMobile } from "../lib/format";
import { normalizeTagCode } from "../lib/rules";
import { MY_CARD_KEY, MY_TAGS_KEY } from "./Account";

function Message({ title, body }: { title: string; body: string }) {
  return (
    <Card>
      <h1 className="text-xl font-bold">{title}</h1>
      <p className="mt-2 text-muted">{body}</p>
      <Link to="/account" className="mt-4 inline-block font-medium text-brand">
        Back to my tags
      </Link>
    </Card>
  );
}

export default function Activate() {
  const code = normalizeTagCode(useParams().code ?? "");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const me = useMe();
  const countdown = useCountdown();
  const [values, setValues] = useState<CardFormValues | null>(null);
  const [sent, setSent] = useState(false);
  const [otp, setOtp] = useState("");

  const tag = useQuery({
    queryKey: ["public-tag", code],
    queryFn: () =>
      api<PublicTag>(`/api/public/tags/${code}`).catch((error) => {
        if (error instanceof ApiError && error.status === 404) return { state: "not_found" } as PublicTag;
        throw error;
      }),
  });
  const card = useQuery({
    queryKey: MY_CARD_KEY,
    queryFn: async () => (await api<{ card: ContactCard | null }>("/api/me/card")).card,
  });

  // Start from the owner's saved card, or from their account name the first time.
  useEffect(() => {
    if (values === null && card.data !== undefined && me.data) {
      setValues(card.data ? cardFromApi(card.data) : emptyCard(me.data.name));
    }
  }, [card.data, me.data, values]);

  const sendCode = useMutation({
    mutationFn: () => api<{ resendAfterSeconds: number }>("/api/me/activation/otp", { method: "POST", body: {} }),
    onSuccess: (res) => {
      countdown.restart(res.resendAfterSeconds);
      setSent(true);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "OTP_COOLDOWN") {
        countdown.restart(error.retryAfterSeconds ?? 60);
        setSent(true);
      }
    },
  });

  const activate = useMutation({
    mutationFn: () =>
      api<{ tag: OwnerTag }>("/api/me/tags/activate", {
        method: "POST",
        body: { code, otp, card: cardPayload(values!) },
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: MY_TAGS_KEY }),
        queryClient.invalidateQueries({ queryKey: MY_CARD_KEY }),
        queryClient.invalidateQueries({ queryKey: ME_KEY }),
      ]);
      navigate(`/account/tags/${code}`, { replace: true, state: { justActivated: true } });
    },
  });

  if (tag.isPending || card.isPending || !me.data || values === null) {
    if (tag.error) return <Alert>{errorMessage(tag.error)}</Alert>;
    return <Loading />;
  }

  if (tag.data?.state === "not_found") {
    return <Message title="Tag not found" body={`We could not find a tag with the code ${code}. Check the code and try again.`} />;
  }
  if (tag.data?.state === "retired") {
    return <Message title="This tag is retired" body="It has been stopped for good and cannot be turned on." />;
  }
  if (tag.data?.state !== "not_active") {
    return <Message title="This tag cannot be turned on" body="It has already been turned on. If you bought it new, please contact support." />;
  }
  if (!tag.data.ready) {
    return (
      <Message
        title="This tag is not ready yet"
        body="It has not been marked as sold. Please buy it from CARTAG or an official seller, or contact support if you already did."
      />
    );
  }

  const issues = activate.error instanceof ApiError ? activate.error.issues : [];
  const codeError = activate.error instanceof ApiError && activate.error.code === "INVALID_OTP" ? activate.error.message : undefined;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!sent) sendCode.mutate();
    else activate.mutate();
  };

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="Turn on your CARTAG" subtitle={`Tag ${code}`} />
      <form onSubmit={submit} className="space-y-5" noValidate>
        {activate.error && issues.length === 0 && !codeError && <Alert>{errorMessage(activate.error)}</Alert>}
        {sendCode.error && !(sendCode.error instanceof ApiError && sendCode.error.code === "OTP_COOLDOWN") && (
          <Alert>{errorMessage(sendCode.error)}</Alert>
        )}

        <Card>
          <h2 className="mb-4 font-semibold">Your contact card</h2>
          <ContactCardFields values={values} onChange={setValues} issues={issues} />
        </Card>

        <Card>
          <h2 className="font-semibold">Confirm your mobile number</h2>
          <p className="mt-1 text-sm text-muted">
            We will text a 6-digit code to <strong>{formatPkMobile(me.data.phone)}</strong>. This confirms that the tag is yours.
          </p>
          {sent && (
            <div className="mt-4 space-y-3">
              <OtpInput value={otp} onChange={setOtp} error={codeError} />
              <Button
                variant="ghost"
                disabled={countdown.left > 0}
                loading={sendCode.isPending}
                onClick={() => sendCode.mutate()}
              >
                {countdown.left > 0 ? `Resend code in ${countdown.left}s` : "Resend code"}
              </Button>
            </div>
          )}
        </Card>

        <Button type="submit" className="w-full" loading={sendCode.isPending || activate.isPending} disabled={sent && otp.length !== 6}>
          {sent ? "Turn on tag" : "Send me a code"}
        </Button>
        <p className="text-center text-sm text-muted">
          Wrong number? <Link to="/account/mobile" className="font-medium text-brand">Change it first</Link>.
        </p>
      </form>
    </div>
  );
}
