"""Domain types shared by tools, data sources, and the valuation engine."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PropertyType(str, Enum):
    SINGLE_FAMILY = "single_family"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"
    MULTI_FAMILY = "multi_family"
    MANUFACTURED = "manufactured"


class Address(BaseModel):
    """US postal address."""

    model_config = ConfigDict(extra="forbid")

    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=2, max_length=2)
    zip: str = Field(pattern=r"^\d{5}$")

    @field_validator("state")
    @classmethod
    def _upper_state(cls, v: str) -> str:
        return v.upper()


class PropertyFacts(BaseModel):
    """Physical attributes that drive a valuation."""

    model_config = ConfigDict(extra="forbid")

    beds: float = Field(ge=0)
    baths: float = Field(ge=0)
    sqft: int = Field(gt=0)
    lot_sqft: int | None = Field(default=None, gt=0)
    year_built: int | None = Field(default=None, ge=1700, le=2100)
    property_type: PropertyType = PropertyType.SINGLE_FAMILY
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class SubjectProperty(BaseModel):
    """The home being valued."""

    model_config = ConfigDict(extra="forbid")

    address: Address
    facts: PropertyFacts


class Comp(BaseModel):
    """A comparable sold property."""

    model_config = ConfigDict(extra="forbid")

    address: Address
    facts: PropertyFacts
    sale_price: float = Field(gt=0)
    sale_date: date
    distance_miles: float = Field(ge=0)
    source: str = "unknown"


class Adjustment(BaseModel):
    """One line of the adjustment grid."""

    model_config = ConfigDict(extra="forbid")

    field: str
    amount: float
    reason: str


class AdjustedComp(Comp):
    """A comp after adjustment, with its derivation kept visible."""

    adjustments: list[Adjustment] = Field(default_factory=list)

    @property
    def net_adjustment(self) -> float:
        return sum(a.amount for a in self.adjustments)

    @property
    def adjusted_price(self) -> float:
        return self.sale_price + self.net_adjustment


class ConfidenceBand(BaseModel):
    """Value range with the confidence score that justifies it."""

    model_config = ConfigDict(extra="forbid")

    low: float = Field(gt=0)
    point: float = Field(gt=0)
    high: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> ConfidenceBand:
        if not self.low <= self.point <= self.high:
            raise ValueError("confidence band must satisfy low <= point <= high")
        return self

    @property
    def spread_pct(self) -> float:
        return (self.high - self.low) / self.point


class Valuation(BaseModel):
    """Full defensible appraisal output."""

    model_config = ConfigDict(extra="forbid")

    subject: SubjectProperty
    comps: list[AdjustedComp] = Field(min_length=1)
    band: ConfidenceBand
    methodology: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def price_per_sqft(self) -> float:
        return self.band.point / self.subject.facts.sqft
