/**
 * Pricing, in one place.
 *
 * These values mirror backend/payments/pricing.py, which remains the authority: checkout
 * sends a plan *code* and the server resolves the amount, so a stale constant here can
 * only ever make the UI wrong, never the charge. Keep the two files in step.
 */

export type PlanCode = "premium_monthly" | "premium_yearly";

export type Plan = {
  code: PlanCode;
  name: string;
  amountNaira: number;
  months: number;
  description: string;
};

export const MONTHLY: Plan = {
  code: "premium_monthly",
  name: "Premium",
  amountNaira: 2999,
  months: 1,
  description: "Full access, billed monthly.",
};

export const YEARLY: Plan = {
  code: "premium_yearly",
  name: "Premium — Yearly",
  amountNaira: 29990,
  months: 12,
  description: "Full access for a year. Two months free versus monthly.",
};

export const PLANS: Record<PlanCode, Plan> = {
  premium_monthly: MONTHLY,
  premium_yearly: YEARLY,
};

export const DEFAULT_PLAN = MONTHLY;

/** Format naira with thousands separators, e.g. 2999 -> "₦2,999". */
export function formatNaira(amount: number): string {
  return `₦${amount.toLocaleString("en-NG")}`;
}

export const MONTHLY_PRICE_LABEL = formatNaira(MONTHLY.amountNaira);
export const YEARLY_PRICE_LABEL = formatNaira(YEARLY.amountNaira);

/** How much a year on the yearly plan saves versus paying monthly. */
export function yearlySavings(): number {
  return MONTHLY.amountNaira * 12 - YEARLY.amountNaira;
}
