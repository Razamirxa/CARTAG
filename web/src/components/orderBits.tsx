import type { DeliveryStatus, OrderStatus, PaymentStatus } from "../lib/api";
import { Badge } from "./ui";

type Tone = "neutral" | "success" | "warn" | "danger" | "brand";

const orderTone: Record<OrderStatus, Tone> = {
  PLACED: "brand",
  PROCESSING: "warn",
  SHIPPED: "brand",
  DELIVERED: "success",
  CANCELLED: "neutral",
};
export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  PLACED: "Placed",
  PROCESSING: "Being prepared",
  SHIPPED: "On its way",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
};

const paymentTone: Record<PaymentStatus, Tone> = {
  DUE: "warn",
  CHECKING: "warn",
  PAID: "success",
  FAILED: "danger",
  CANCELLED: "neutral",
  REFUNDED: "neutral",
  COD_PENDING: "neutral",
  COD_COLLECTED: "success",
};
export const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  DUE: "Payment due",
  CHECKING: "Checking payment",
  PAID: "Paid",
  FAILED: "Payment failed",
  CANCELLED: "Payment cancelled",
  REFUNDED: "Refunded",
  COD_PENDING: "Pay on delivery",
  COD_COLLECTED: "Cash collected",
};

export const DELIVERY_STATUS_LABEL: Record<DeliveryStatus, string> = {
  NOT_BOOKED: "Not booked yet",
  BOOKED: "Booked",
  IN_TRANSIT: "In transit",
  DELIVERED: "Delivered",
  FAILED: "Delivery failed",
  RETURNED: "Returned",
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return <Badge tone={orderTone[status]}>{ORDER_STATUS_LABEL[status]}</Badge>;
}

export function PaymentBadge({ status }: { status: PaymentStatus }) {
  return <Badge tone={paymentTone[status]}>{PAYMENT_STATUS_LABEL[status]}</Badge>;
}

export const COLOUR_SWATCH: Record<string, string> = {
  BLACK: "#0a0a0a",
  IVORY: "#f5f1e8",
  BURGUNDY: "#74152b",
  GLACIER: "#b9d8e8",
};

export const SIZE_LABEL: Record<string, string> = { COMPACT: "Compact", STANDARD: "Standard", LARGE: "Large" };
export const COLOUR_LABEL: Record<string, string> = {
  BLACK: "Black",
  IVORY: "Ivory",
  BURGUNDY: "Burgundy",
  GLACIER: "Glacier",
};
