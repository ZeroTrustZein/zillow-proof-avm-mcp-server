"""Core sales-comparison engine: adjust comps, weight them, reconcile a band.

Every number the engine emits is traceable: each adjustment carries its field,
amount, and reason, and the band's confidence is a weighted blend of dispersion,
comp count, and proximity. No black boxes.
"""

from __future__ import annotations

import math
from datetime import date

from .models import (
    AdjustedComp,
    Adjustment,
    Comp,
    ConfidenceBand,
    PropertyFacts,
    SubjectProperty,
    Valuation,
)

# Adjustment rates, expressed as fractions of a comp's sale price per unit of difference.
BED_RATE = 0.015
BATH_RATE = 0.010
YEAR_RATE = 0.003
LOT_RATE_PER_1K_SQFT = 0.010
MAX_YEAR_DIFF = 30
# GLA is worth roughly half the market $/sqft; full $/sqft double-counts land and improvements.
GLA_RATE_FACTOR = 0.5
# Comps older than this many days get no weight (half-life decay).
RECENCY_HALF_LIFE_DAYS = 90.0


def _gla_rate(comp: Comp) -> float:
    return (comp.sale_price / comp.facts.sqft) * GLA_RATE_FACTOR


def adjust_comp(subject: PropertyFacts, comp: Comp) -> AdjustedComp:
    """Adjust ``comp`` to the subject's characteristics, line by line."""
    price = comp.sale_price
    lines: list[Adjustment] = []

    sqft_diff = subject.sqft - comp.facts.sqft
    if sqft_diff:
        rate = _gla_rate(comp)
        lines.append(
            Adjustment(
                field="sqft",
                amount=round(sqft_diff * rate, 2),
                reason=f"{sqft_diff:+d} sqft @ ${rate:,.0f}/sqft (50% of comp $/sqft)",
            )
        )

    beds_diff = subject.beds - comp.facts.beds
    if beds_diff:
        lines.append(
            Adjustment(
                field="beds",
                amount=round(beds_diff * price * BED_RATE, 2),
                reason=f"{beds_diff:+g} bed @ {BED_RATE:.1%} of price",
            )
        )

    baths_diff = subject.baths - comp.facts.baths
    if baths_diff:
        lines.append(
            Adjustment(
                field="baths",
                amount=round(baths_diff * price * BATH_RATE, 2),
                reason=f"{baths_diff:+g} bath @ {BATH_RATE:.1%} of price",
            )
        )

    if subject.lot_sqft and comp.facts.lot_sqft:
        lot_diff = subject.lot_sqft - comp.facts.lot_sqft
        if lot_diff:
            lines.append(
                Adjustment(
                    field="lot_sqft",
                    amount=round((lot_diff / 1000) * price * LOT_RATE_PER_1K_SQFT, 2),
                    reason=f"{lot_diff:+d} sqft lot @ {LOT_RATE_PER_1K_SQFT:.1%} per 1,000 sqft",
                )
            )

    if subject.year_built and comp.facts.year_built:
        year_diff = max(-MAX_YEAR_DIFF, min(MAX_YEAR_DIFF, subject.year_built - comp.facts.year_built))
        if year_diff:
            lines.append(
                Adjustment(
                    field="year_built",
                    amount=round(year_diff * price * YEAR_RATE, 2),
                    reason=f"{year_diff:+d} yr @ {YEAR_RATE:.1%} of price (capped at {MAX_YEAR_DIFF} yr)",
                )
            )

    return AdjustedComp(
        **comp.model_dump(),
        adjustments=[line for line in lines if line.amount],
    )


def select_comps(
    comps: list[Comp],
    subject: SubjectProperty,
    *,
    max_distance_miles: float = 2.0,
    max_age_days: int = 180,
    limit: int = 8,
    today: date | None = None,
) -> list[Comp]:
    """Keep proximate, recent, same-type comps; closest and newest first."""
    today = today or date.today()
    kept = [
        c
        for c in comps
        if c.facts.property_type == subject.facts.property_type
        and c.distance_miles <= max_distance_miles
        and (today - c.sale_date).days <= max_age_days
    ]
    kept.sort(key=lambda c: ((today - c.sale_date).days, c.distance_miles))
    return kept[:limit]


def comp_weight(comp: Comp, today: date | None = None) -> float:
    """Weight by proximity and recency; closer and newer comps dominate."""
    today = today or date.today()
    age_days = max((today - comp.sale_date).days, 0)
    recency = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)
    proximity = 1.0 / (1.0 + comp.distance_miles)
    return recency * proximity


def reconcile(comps: list[AdjustedComp], today: date | None = None) -> ConfidenceBand:
    """Weighted mean of adjusted prices, with a dispersion-driven band and confidence."""
    if not comps:
        raise ValueError("at least one adjusted comp is required")

    weights = [comp_weight(c, today) for c in comps]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("all comps have zero weight (too old)")

    point = sum(w * c.adjusted_price for w, c in zip(weights, comps)) / total_weight
    variance = sum(w * (c.adjusted_price - point) ** 2 for w, c in zip(weights, comps)) / total_weight
    dispersion = math.sqrt(variance)

    mean_distance = sum(w * c.distance_miles for w, c in zip(weights, comps)) / total_weight
    count_score = min(len(comps) / 6, 1.0)
    spread_score = max(0.0, min(1.0, 1.0 - (dispersion / point) * 5))
    proximity_score = max(0.0, min(1.0, 1.0 - mean_distance / 2))
    confidence = max(0.05, min(0.95, 0.45 * spread_score + 0.35 * count_score + 0.20 * proximity_score))

    half_width = min(max(dispersion, point * 0.03), point * 0.5)
    return ConfidenceBand(
        low=math.floor(point - half_width),
        point=round(point, 2),
        high=math.ceil(point + half_width),
        confidence=round(confidence, 3),
    )


METHODOLOGY = (
    "Sales comparison approach: subject characteristics drive line-item adjustments to each "
    "recent, proximate, same-type sale (GLA at 50% of comp $/sqft, beds 1.5%, baths 1.0%, "
    "year built 0.3%/yr capped at 30, lot 1.0% per 1,000 sqft). Adjusted prices are reconciled "
    "by a proximity-and-recency weight; the confidence band spans one weighted standard "
    "deviation (floored at 3% and capped at 50% of the point estimate)."
)


def value_property(
    subject: SubjectProperty,
    comps: list[Comp],
    *,
    max_distance_miles: float = 2.0,
    max_age_days: int = 180,
    min_comps: int = 3,
    limit: int = 8,
    today: date | None = None,
) -> Valuation:
    """Full defensible valuation from raw comps."""
    today = today or date.today()
    selected = select_comps(
        comps,
        subject,
        max_distance_miles=max_distance_miles,
        max_age_days=max_age_days,
        limit=limit,
        today=today,
    )
    if len(selected) < min_comps:
        raise ValueError(
            f"only {len(selected)} usable comps within {max_distance_miles} mi and "
            f"{max_age_days} days; need at least {min_comps}"
        )

    adjusted = [adjust_comp(subject.facts, c) for c in selected]
    return Valuation(
        subject=subject,
        comps=adjusted,
        band=reconcile(adjusted, today),
        methodology=METHODOLOGY,
    )
