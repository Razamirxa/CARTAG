export interface FieldIssue {
  field: string;
  message: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Seconds the server asked us to wait, for rate-limit and lock responses. */
  get retryAfterSeconds(): number | undefined {
    const value = (this.details as { retryAfterSeconds?: number } | undefined)?.retryAfterSeconds;
    return typeof value === "number" ? value : undefined;
  }

  get issues(): FieldIssue[] {
    return this.code === "VALIDATION_ERROR" && Array.isArray(this.details) ? (this.details as FieldIssue[]) : [];
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function api<T>(path: string, options: { method?: Method; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: options.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Could not reach the server. Check your internet connection and try again.");
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const error = (data as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "ERROR",
      error?.message ?? "Something went wrong. Please try again.",
      error?.details,
    );
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}

/* ---------- response shapes ---------- */

export interface Owner {
  id: string;
  name: string;
  phone: string;
  phoneVerified: boolean;
  hasCard: boolean;
  createdAt: string;
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
}

export type TagStatus = "NOT_ACTIVE" | "ACTIVE" | "TURNED_OFF" | "RETIRED";
export type StockStatus = "IN_STOCK" | "RESERVED" | "SOLD" | "DAMAGED" | "REPLACED";

export interface ContactCard {
  displayName: string;
  emergencyEnabled: boolean;
  bloodGroup: string | null;
  emergencyName: string | null;
  emergencyRelationship: string | null;
  emergencyPhone: string | null;
}

export interface OwnerTag {
  code: string;
  serial: string;
  status: TagStatus;
  activatedAt: string | null;
}

export type PublicTag =
  | { state: "not_found" }
  | { state: "not_active"; code: string; ready: boolean }
  | { state: "turned_off" }
  | { state: "retired" }
  | { state: "active"; code: string };

export interface AdminTag {
  code: string;
  serial: string;
  status: TagStatus;
  stockStatus: StockStatus;
  batch: { id: string; name: string };
  owner: { id: string; name: string; phone: string } | null;
  activatedAt: string | null;
  retiredAt: string | null;
  createdAt: string;
}

export interface Page<T> {
  total: number;
  page: number;
  pageSize: number;
  items: T[];
}

export interface Batch {
  id: string;
  name: string;
  quantity: number;
  source: "GENERATED" | "IMPORTED";
  baseUrl: string;
  createdAt: string;
  byStatus: Partial<Record<TagStatus, number>>;
}

export interface DeletionRequest {
  id: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reason: string | null;
  requestedAt: string;
  decidedAt: string | null;
}

export type ProductSize = "COMPACT" | "STANDARD" | "LARGE";
export type ProductColour = "BLACK" | "IVORY" | "BURGUNDY" | "GLACIER";

export interface Product {
  sku: string;
  size: ProductSize;
  colour: ProductColour;
  premium: boolean;
  name: string;
  description: string | null;
  price: number;
  active: boolean;
}

export type OrderStatus = "PLACED" | "PROCESSING" | "SHIPPED" | "DELIVERED" | "CANCELLED";
export type PaymentMethod = "COD" | "PREPAID";
export type PaymentStatus =
  | "DUE"
  | "CHECKING"
  | "PAID"
  | "FAILED"
  | "CANCELLED"
  | "REFUNDED"
  | "COD_PENDING"
  | "COD_COLLECTED";
export type DeliveryStatus = "NOT_BOOKED" | "BOOKED" | "IN_TRANSIT" | "DELIVERED" | "FAILED" | "RETURNED";

export interface OrderItem {
  sku: string;
  name: string;
  unitPrice: number;
  quantity: number;
  lineTotal: number;
}

export interface Order {
  number: number;
  label: string;
  status: OrderStatus;
  paymentMethod: PaymentMethod;
  paymentStatus: PaymentStatus;
  subtotal: number;
  shippingFee: number;
  total: number;
  recipient: { name: string; phone: string; address: string; city: string; notes: string | null };
  delivery: { courier: string | null; trackingNumber: string | null; status: DeliveryStatus };
  createdAt: string;
  paidAt: string | null;
  shippedAt: string | null;
  deliveredAt: string | null;
  cancelledAt: string | null;
  items?: OrderItem[];
}

export interface AdminOrder extends Order {
  customer: { id?: string; name: string; phone: string };
  payments?: Array<{
    id: string;
    provider: string;
    status: string;
    amount: number;
    reference: string | null;
    createdAt: string;
    confirmedAt: string | null;
  }>;
}
