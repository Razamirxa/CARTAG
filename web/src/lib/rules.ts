/** Small rules the browser needs. The server enforces the real ones, so these only improve the form. */

export const TAG_STATUSES = ["NOT_ACTIVE", "ACTIVE", "TURNED_OFF", "RETIRED"] as const;
export const STOCK_STATUSES = ["IN_STOCK", "RESERVED", "SOLD", "DAMAGED", "REPLACED"] as const;
export const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] as const;

export const MAX_BATCH_SIZE = 100_000;

// Same alphabet as the server: no I, L, O or U, so printed codes cannot be misread.
const TAG_CODE_PATTERN = /^[0-9ABCDEFGHJKMNPQRSTVWXYZ]{6,24}$/;

export const normalizeTagCode = (input: string) => input.trim().toUpperCase();
export const isValidTagCode = (code: string) => TAG_CODE_PATTERN.test(code);

/** Formats an E.164 Pakistani number for display: 0300 1234567. */
export function formatPkMobile(e164: string): string {
  const digits = e164.replace(/^\+92/, "");
  if (!/^3\d{9}$/.test(digits)) return e164;
  return `0${digits.slice(0, 3)} ${digits.slice(3)}`;
}
