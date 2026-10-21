from datetime import date

import pytest
from pydantic import ValidationError

from zillow_proof_avm_mcp.models import (
    Address,
    AdjustedComp,
    Adjustment,
    Comp,
    ConfidenceBand,
    PropertyFacts,
    PropertyType,
    SubjectProperty,
    Valuation,
)

ADDR = Address(street="1 Main St", city="Austin", state="tx", zip="78701")
FACTS = PropertyFacts(beds=3, baths=2, sqft=2000, lot_sqft=6000, year_built=1998)


def _comp(price=400_000):
    return Comp(
        address=ADDR,
        facts=FACTS,
        sale_price=price,
        sale_date=date(2026, 6, 1),
        distance_miles=0.4,
    )


def test_address_normalizes_state():
    assert ADDR.state == "TX"


def test_address_rejects_bad_zip():
    with pytest.raises(ValidationError):
        Address(street="1 Main St", city="Austin", state="TX", zip="787")


def test_facts_reject_zero_sqft():
    with pytest.raises(ValidationError):
        PropertyFacts(beds=3, baths=2, sqft=0)


def test_facts_default_property_type():
    assert FACTS.property_type is PropertyType.SINGLE_FAMILY


def test_facts_reject_unknown_field():
    with pytest.raises(ValidationError):
        PropertyFacts(beds=3, baths=2, sqft=2000, pool=True)


def test_adjusted_comp_math():
    a = Adjustment(field="sqft", amount=-5_000, reason="-200 sqft @ $25")
    c = AdjustedComp(**_comp().model_dump(), adjustments=[a])
    assert c.net_adjustment == -5_000
    assert c.adjusted_price == 395_000


def test_band_ordering_enforced():
    with pytest.raises(ValidationError):
        ConfidenceBand(low=500_000, point=400_000, high=450_000, confidence=0.7)


def test_band_spread():
    band = ConfidenceBand(low=380_000, point=400_000, high=420_000, confidence=0.8)
    assert band.spread_pct == pytest.approx(0.1)


def test_valuation_requires_comps():
    band = ConfidenceBand(low=380_000, point=400_000, high=420_000, confidence=0.8)
    with pytest.raises(ValidationError):
        Valuation(
            subject=SubjectProperty(address=ADDR, facts=FACTS),
            comps=[],
            band=band,
            methodology="sales comparison",
        )


def test_valuation_price_per_sqft():
    band = ConfidenceBand(low=380_000, point=400_000, high=420_000, confidence=0.8)
    v = Valuation(
        subject=SubjectProperty(address=ADDR, facts=FACTS),
        comps=[AdjustedComp(**_comp().model_dump())],
        band=band,
        methodology="sales comparison",
    )
    assert v.price_per_sqft == pytest.approx(200.0)
