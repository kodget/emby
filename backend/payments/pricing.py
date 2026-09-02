"""
The single source of truth for what Emby costs.

Prices used to be hardcoded in five separate frontend files *and* taken from the request
body at checkout, which meant the displayed price and the charged price could disagree
and a crafted request could buy premium for one naira. Everything now resolves a plan
code to a price here, on the server; the client only ever names a plan.

Amounts are whole naira. Paystack is charged in kobo, so `amount_kobo` is the only place
that conversion happens.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    amount_naira: int
    months: int
    description: str
    paystack_plan_code: str | None = None

    @property
    def amount_kobo(self) -> int:
        return self.amount_naira * 100

    @property
    def display_price(self) -> str:
        return f"₦{self.amount_naira:,}"

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "amount_naira": self.amount_naira,
            "amount_kobo": self.amount_kobo,
            "months": self.months,
            "description": self.description,
            "display_price": self.display_price,
            "paystack_plan_code": self.paystack_plan_code,
        }


MONTHLY = Plan(
    code="premium_monthly",
    name="Emby Premium — Monthly",
    amount_naira=2999,
    months=1,
    description="Full access, billed monthly.",
    paystack_plan_code="PLN_188785guod742lv",
)

YEARLY = Plan(
    code="premium_yearly",
    name="Emby Premium — Yearly",
    amount_naira=29990,          # ten months for twelve
    months=12,
    description="Full access for a year. Two months free versus monthly.",
    paystack_plan_code="PLN_vz4b7a5m15kfzh6",
)

PLANS: dict[str, Plan] = {p.code: p for p in (MONTHLY, YEARLY)}

DEFAULT_PLAN = MONTHLY


def get_plan(code: str | None) -> Plan | None:
    """Resolve a plan code. Returns None for anything unrecognised."""
    if not code:
        return DEFAULT_PLAN
    return PLANS.get(str(code).strip().lower())


def all_plans() -> list[dict]:
    return [p.as_dict() for p in PLANS.values()]
