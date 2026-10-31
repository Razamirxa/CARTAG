export { formatPkMobile } from "./rules";

const dateTime = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });

export const formatDateTime = (value: string | null | undefined) => (value ? dateTime.format(new Date(value)) : "—");
export const formatDate = (value: string | null | undefined) => (value ? dateOnly.format(new Date(value)) : "—");

export const vehicleLabel = (type: "CAR" | "BIKE" | null | undefined) =>
  type === "CAR" ? "Car" : type === "BIKE" ? "Bike" : "—";

/** Only allow redirects to pages inside this site. */
export function safeNext(value: string | null, fallback: string): string {
  if (value && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\")) return value;
  return fallback;
}

/** 1200 becomes "Rs 1,200". */
export const rs = (amount: number) => `Rs ${amount.toLocaleString("en-PK")}`;
