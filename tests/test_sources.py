import json

import pytest

from zillow_proof_avm_mcp.config import Config
from zillow_proof_avm_mcp.geo import haversine_miles, miles_between
from zillow_proof_avm_mcp.models import PropertyFacts, SubjectProperty
from zillow_proof_avm_mcp.sources import (
    JsonCompSource,
    StaticCompSource,
    comp_from_record,
    source_from_config,
)
from zillow_proof_avm_mcp.valuation import value_property

FACTS = {"beds": 3, "baths": 2, "sqft": 1800, "latitude": 30.2672, "longitude": -97.7431}
SUBJECT = {
    "address": {"street": "1 Main St", "city": "Austin", "state": "tx", "zip": "78704"},
    "facts": FACTS,
}


def _record(**overrides) -> dict:
    record = {
        "address": {"street": "2 Oak Ave", "city": "Austin", "state": "TX", "zip": "78704"},
        "facts": {"beds": 3, "baths": 2, "sqft": 1750, "latitude": 30.2500, "longitude": -97.7500},
        "sale_price": 620000.0,
        "sale_date": "2026-09-01",
        "source": "fixture",
    }
    record.update(overrides)
    return record


def test_haversine_known_distance():
    # Austin -> Dallas is roughly 180 miles.
    assert 175 < haversine_miles(30.2672, -97.7431, 32.7767, -96.7970) < 190


def test_haversine_zero():
    assert haversine_miles(30.0, -97.0, 30.0, -97.0) == pytest.approx(0.0)


def test_miles_between_missing_coords():
    bare = PropertyFacts(beds=3, baths=2, sqft=1800)
    assert miles_between(bare, bare) is None


def test_miles_between_partial_coords():
    located = PropertyFacts(beds=3, baths=2, sqft=1800, latitude=30.2672, longitude=-97.7431)
    half = PropertyFacts(beds=3, baths=2, sqft=1800, latitude=30.2672)
    assert miles_between(located, half) is None


def test_haversine_is_symmetric():
    a = haversine_miles(30.2672, -97.7431, 32.7767, -96.7970)
    b = haversine_miles(32.7767, -96.7970, 30.2672, -97.7431)
    assert a == pytest.approx(b)


def test_comp_from_record_derives_distance():
    comp = comp_from_record(SubjectProperty(**SUBJECT), _record())
    assert comp.distance_miles > 0


def test_comp_from_record_without_distance_or_coords():
    record = _record(facts={"beds": 3, "baths": 2, "sqft": 1750})
    with pytest.raises(ValueError, match="neither"):
        comp_from_record(SubjectProperty(**SUBJECT), record)


def test_json_source_round_trip(tmp_path):
    path = tmp_path / "comps.json"
    path.write_text(json.dumps({"comps": [_record(distance_miles=0.4)]}), encoding="utf-8")
    subject = SubjectProperty(**SUBJECT)

    comps = JsonCompSource(path).comps_for(subject)

    assert len(comps) == 1
    assert comps[0].distance_miles == 0.4
    assert value_property(subject, comps, min_comps=1).comps[0].adjusted_price > 0


def test_static_source_returns_copy():
    subject = SubjectProperty(**SUBJECT)
    record = _record(distance_miles=1.0, facts={"beds": 3, "baths": 2, "sqft": 1750})
    source = StaticCompSource([comp_from_record(subject, record)])

    first, second = source.comps_for(subject), source.comps_for(subject)

    assert first == second and first is not second


def test_source_from_config_requires_file():
    with pytest.raises(ValueError, match="ZPAVM_COMPS_FILE"):
        source_from_config(Config())
