import type { ContactCard, FieldIssue } from "../lib/api";
import { BLOOD_GROUPS } from "../lib/rules";
import { Field, Input, Select, Toggle } from "./ui";

export interface CardFormValues {
  displayName: string;
  emergencyEnabled: boolean;
  bloodGroup: string;
  emergencyName: string;
  emergencyRelationship: string;
  emergencyPhone: string;
}

export const emptyCard = (displayName = ""): CardFormValues => ({
  displayName,
  emergencyEnabled: false,
  bloodGroup: "",
  emergencyName: "",
  emergencyRelationship: "",
  emergencyPhone: "",
});

export function cardFromApi(card: ContactCard): CardFormValues {
  return {
    displayName: card.displayName,
    emergencyEnabled: card.emergencyEnabled,
    bloodGroup: card.bloodGroup ?? "",
    emergencyName: card.emergencyName ?? "",
    emergencyRelationship: card.emergencyRelationship ?? "",
    emergencyPhone: card.emergencyPhone ?? "",
  };
}

/** Turns the form into the request body. Empty text is sent as "" and the server stores it as nothing. */
export function cardPayload(values: CardFormValues) {
  return { ...values, bloodGroup: values.bloodGroup || null };
}

export function issueFor(issues: FieldIssue[], field: string): string | undefined {
  return issues.find((i) => i.field === field || i.field.endsWith(`.${field}`))?.message;
}

export function ContactCardFields({
  values,
  onChange,
  issues,
}: {
  values: CardFormValues;
  onChange: (next: CardFormValues) => void;
  issues: FieldIssue[];
}) {
  const set = <K extends keyof CardFormValues>(key: K, value: CardFormValues[K]) => onChange({ ...values, [key]: value });

  return (
    <div className="space-y-4">
      <Field label="Your name" error={issueFor(issues, "displayName")} hint="Shown on your scan page.">
        <Input
          value={values.displayName}
          onChange={(e) => set("displayName", e.target.value)}
          autoComplete="name"
          maxLength={80}
          required
        />
      </Field>

      <p className="rounded-xl bg-subtle px-4 py-3 text-sm text-muted">
        Your mobile number is never shown as text. It is only used by the Call Owner and WhatsApp Owner buttons.
      </p>

      <div className="rounded-xl border border-line px-4 pb-4 pt-2">
        <Toggle
          label="Emergency Mode"
          hint="Show your blood group and one emergency contact on your scan page. You can turn this off at any time."
          checked={values.emergencyEnabled}
          onChange={(v) => set("emergencyEnabled", v)}
        />
        {values.emergencyEnabled && (
          <div className="mt-2 space-y-4 border-t border-line pt-4">
            <Field label="Blood group (optional)" error={issueFor(issues, "bloodGroup")}>
              <Select value={values.bloodGroup} onChange={(e) => set("bloodGroup", e.target.value)}>
                <option value="">Do not show</option>
                {BLOOD_GROUPS.map((group) => (
                  <option key={group} value={group}>
                    {group}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Emergency contact name" error={issueFor(issues, "emergencyName")}>
              <Input value={values.emergencyName} onChange={(e) => set("emergencyName", e.target.value)} maxLength={80} />
            </Field>
            <Field
              label="Relationship"
              error={issueFor(issues, "emergencyRelationship")}
              hint="For example wife, brother, friend."
            >
              <Input
                value={values.emergencyRelationship}
                onChange={(e) => set("emergencyRelationship", e.target.value)}
                maxLength={40}
              />
            </Field>
            <Field
              label="Emergency contact mobile"
              error={issueFor(issues, "emergencyPhone")}
              hint="Used by the Call button only, not shown as text."
            >
              <Input
                type="tel"
                inputMode="tel"
                value={values.emergencyPhone}
                onChange={(e) => set("emergencyPhone", e.target.value)}
                placeholder="03XX XXXXXXX"
              />
            </Field>
          </div>
        )}
      </div>
    </div>
  );
}
