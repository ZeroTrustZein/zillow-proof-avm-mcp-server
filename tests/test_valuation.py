from datetime import date, timedelta

import pytest

from zillow_proof_avm_mcp.models import (
    Address,
    Comp,
    PropertyFacts,
    PropertyType,
    SubjectProperty,
)
from zillow_proof_avm_mcp.valuation import (
    adjust_comp,
    comp_weight,
    reconcile,
    select_comps,
    value_property,
)

TODAY = date(2026, 6, 30)
ADDR = Address(street="1 Main St", city="Austin", state="TX", zip="78701")
SUBJECT_FACTS = PropertyFacts(beds=3, baths=2, sqft=2000, lot_sqft=6000, year_built=2000)
SUBJECT = SubjectProperty(address=ADDR, facts=SUBJECT_FACTS)


def _comp(
    price=400_000,
    sqft=2000,
    distance=0.4,
    days_ago=30,
    ptype=PropertyType.SINGLE_FAMILY,
    beds=3,
    baths=2,
    year_built=2000,
):
    return Comp(
        address=ADDR,
        facts=PropertyFacts(
            beds=beds,
            baths=baths,
            sqft=sqft,
            lot_sqft=6000,
            year_built=year_built,
            property_type=ptype,
        ),
        sale_price=price,
        sale_date=TODAY - timedelta(days=days_ago),
        distance_miles=distance,
    )


def test_identical_comp_needs_no_adjustments():
    adjusted = adjust_comp(SUBJECT_FACTS, _comp())
    assert adjusted.adjustments == []
    assert adjusted.adjusted_price == 400_000


def test_gla_adjustment_uses_half_rate():
    adjusted = adjust_comp(SUBJECT_FACTS, _comp(sqft=1800))
    line = next(a for a in adjusted.adjustments if a.field == "sqft")
    # 200 sqft * (400k / 1800) * 0.5
    assert line.amount == pytest.approx(200 * (400_000 / 1800) * 0.5, rel=1e-6)
    assert adjusted.adjusted_price == pytest.approx(400_000 + line.amount)


def test_every_adjustment_has_a_reason():
    adjusted = adjust_comp(
        SUBJECT_FACTS,
        _comp(sqft=1700, beds=2, baths=1.5),
    )
    assert len(adjusted.adjustments) >= 3
    assert all(a.reason and a.field and a.amount for a in adjusted.adjustments)


def test_select_comps_filters_type_distance_age():
    comps = [
        _comp(),
        _comp(ptype=PropertyType.CONDO),
        _comp(distance=9.0),
        _comp(days_ago=400),
    ]
    kept = select_comps(comps, SUBJECT, today=TODAY)
    assert len(kept) == 1


def test_select_comps_orders_newest_then_closest():
    comps = [_comp(days_ago=90, distance=0.1), _comp(days_ago=10, distance=0.9)]
    kept = select_comps(comps, SUBJECT, today=TODAY)
    assert kept[0].sale_date == TODAY - timedelta(days=10)


def test_select_comps_respects_limit():
    comps = [_comp() for _ in range(12)]
    assert len(select_comps(comps, SUBJECT, limit=5, today=TODAY)) == 5


def test_weight_decays_with_distance_and_age():
    near_new = comp_weight(_comp(distance=0.2, days_ago=10), TODAY)
    far_old = comp_weight(_comp(distance=1.9, days_ago=170), TODAY)
    assert near_new > far_old


def test_reconcile_averages_adjusted_prices():
    comps = [adjust_comp(SUBJECT_FACTS, _comp(price=p)) for p in (380_000, 400_000, 420_000)]
    band = reconcile(comps, TODAY)
    assert band.point == pytest.approx(400_000, rel=0.02)
    assert band.low <= band.point <= band.high


def test_reconcile_tighter_band_for_agreeing_comps():
    tight = reconcile([adjust_comp(SUBJECT_FACTS, _comp(price=p)) for p in (399_000, 400_000, 401_000)], TODAY)
    wide = reconcile([adjust_comp(SUBJECT_FACTS, _comp(price=p)) for p in (300_000, 400_000, 500_000)], TODAY)
    assert tight.spread_pct < wide.spread_pct
    assert tight.confidence > wide.confidence


def test_reconcile_rejects_empty():
    with pytest.raises(ValueError):
        reconcile([], TODAY)


def test_value_property_end_to_end():
    comps = [_comp(price=390_000 + i * 10_000) for i in range(4)]
    valuation = value_property(SUBJECT, comps, today=TODAY)
    assert len(valuation.comps) == 4
    assert valuation.band.point > 0
    assert valuation.methodology.startswith("Sales comparison approach")
    assert valuation.created_at is not None


def test_value_property_raises_when_too_few_comps():
    with pytest.raises(ValueError, match="need at least 3"):
        value_property(SUBJECT, [_comp()], today=TODAY)


def test_year_adjustment_is_capped():
    line = next(
        a for a in adjust_comp(SUBJECT_FACTS, _comp(year_built=1950)).adjustments
        if a.field == "year_built"
    )
    assert line.amount == pytest.approx(30 * 400_000 * 0.003, rel=1e-6)
    assert line.reason.endswith("capped at 30 yr)")


def test_lot_adjustment_skipped_without_subject_lot():
    facts = SUBJECT_FACTS.model_copy(update={"lot_sqft": None})
    adjusted = adjust_comp(facts, _comp())
    assert all(a.field != "lot_sqft" for a in adjusted.adjustments)


def test_lot_adjustment_scales_per_thousand_sqft():
    adjusted = adjust_comp(SUBJECT_FACTS, _comp())
    assert adjusted.adjustments == []
    bigger = SUBJECT_FACTS.model_copy(update={"lot_sqft": 8000})
    line = adjust_comp(bigger, _comp()).adjustments[0]
    assert line.field == "lot_sqft"
    assert line.amount == pytest.approx(2 * 400_000 * 0.010, rel=1e-6)


def test_reconcile_rejects_comps_with_no_weight():
    stale = adjust_comp(SUBJECT_FACTS, _comp(days_ago=200_000))  # recency term underflows to 0
    with pytest.raises(ValueError, match="zero weight"):
        reconcile([stale], TODAY)


def test_band_width_has_three_percent_floor():
    band = reconcile([adjust_comp(SUBJECT_FACTS, _comp(price=p)) for p in (400_000, 400_000)], TODAY)
    assert band.spread_pct == pytest.approx(0.06, abs=1e-3)


def test_confidence_stays_within_bounds():
    tight = reconcile([adjust_comp(SUBJECT_FACTS, _comp(price=400_000)) for _ in range(10)], TODAY)
    wild = reconcile(
        [adjust_comp(SUBJECT_FACTS, _comp(price=p)) for p in (100_000, 700_000)], TODAY
    )
    assert 0.05 <= wild.confidence <= tight.confidence <= 0.95


def test_select_comps_thresholds_are_overridable():
    comps = [_comp(distance=3.0, days_ago=200)]
    assert select_comps(comps, SUBJECT, today=TODAY) == []
    kept = select_comps(
        comps, SUBJECT, max_distance_miles=5.0, max_age_days=365, today=TODAY
    )
    assert len(kept) == 1
