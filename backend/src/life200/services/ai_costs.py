"""What each AI call cost, so prices can be set from real numbers.

Prices are list prices in US dollars per million tokens. "Out" includes thinking tokens,
which both providers bill as output. On Gemini's free tier the real bill is $0, but the
list price is still recorded: it is what a paying deployment would spend.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import Connection, Engine, select

from life200.db.models import AiUsageRow, UserRow

# (input, output) USD per 1M tokens, with the date each price starts. Newest last.
PRICES: dict[str, list[tuple[date, Decimal, Decimal]]] = {
    "claude-opus-5-5": [(date(2026, 1, 1), Decimal("4"), Decimal("20"))],
    "claude-sonnet-5-5": [(date(2026, 1, 1), Decimal("2"), Decimal("10"))],
    "claude-haiku-5-5": [(date(2026, 1, 1), Decimal("0.10"), Decimal("0.50"))],
    # Introductory rate until 2026-12-31, then the standard rate (third-party sources,
    # not confirmed on ai.google.dev/pricing).
    "gemini-3.8-flash": [
        (date(2026, 1, 1), Decimal("0.75"), Decimal("3.75")),
        (date(2027, 1, 1), Decimal("1.50"), Decimal("7.50")),
    ],
}
MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class Usage:
    provider: str  # "anthropic" or "google"
    model: str
    input_tokens: int
    output_tokens: int  # including thinking tokens


def cost_usd(usage: Usage, on: date | None = None) -> Decimal | None:
    """List-price cost of one call, or None when the model's price is unknown."""
    prices = PRICES.get(usage.model)
    if not prices:
        return None
    on = on or date.today()
    current = [p for p in prices if p[0] <= on] or prices[:1]
    _, per_in, per_out = current[-1]
    return (usage.input_tokens * per_in + usage.output_tokens * per_out) / MILLION


def record(
    session: object, user_id: int, feature: str, usage: Usage, job_id: int | None = None
) -> AiUsageRow:
    row = AiUsageRow(
        user_id=user_id,
        job_id=job_id,
        feature=feature,
        provider=usage.provider,
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=cost_usd(usage),
    )
    session.add(row)  # type: ignore[attr-defined]
    return row


def usage_table(bind: Engine | Connection) -> pd.DataFrame:
    stmt = (
        select(
            AiUsageRow.created_at,
            UserRow.email,
            AiUsageRow.feature,
            AiUsageRow.model,
            AiUsageRow.input_tokens,
            AiUsageRow.output_tokens,
            AiUsageRow.cost_usd,
        )
        .join(UserRow, UserRow.id == AiUsageRow.user_id)
        .order_by(AiUsageRow.created_at.desc())
    )
    if isinstance(bind, Connection):
        rows = bind.execute(stmt).all()
    else:
        with bind.connect() as conn:
            rows = conn.execute(stmt).all()
    df = pd.DataFrame(
        rows, columns=["When", "User", "Feature", "Model", "Tokens in", "Tokens out", "Cost (USD)"]
    )
    df["Cost (USD)"] = pd.to_numeric(df["Cost (USD)"])
    return df
