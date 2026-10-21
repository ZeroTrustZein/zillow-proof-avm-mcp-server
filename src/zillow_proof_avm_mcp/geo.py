"""Great-circle distance, so comps can be positioned from coordinates alone."""

from __future__ import annotations

import math

from .models import PropertyFacts

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles between two points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def miles_between(a: PropertyFacts, b: PropertyFacts) -> float | None:
    """Distance in miles, or None when either side lacks coordinates."""
    if a.latitude is None or a.longitude is None or b.latitude is None or b.longitude is None:
        return None
    return haversine_miles(a.latitude, a.longitude, b.latitude, b.longitude)
