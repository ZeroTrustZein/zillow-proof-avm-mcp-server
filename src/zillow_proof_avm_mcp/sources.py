"""Comp sources: where candidate sales come from, decoupled from the engine.

A source answers one question — "what recently sold near this subject?" — and
returns plain ``Comp`` objects. Distance is derived from coordinates when a
record omits it, which is the common shape of county and MLS exports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Config
from .geo import miles_between
from .models import Comp, PropertyFacts, SubjectProperty


class CompSource(Protocol):
    """Anything that can produce candidate comps for a subject."""

    def comps_for(self, subject: SubjectProperty) -> list[Comp]: ...


def comp_from_record(subject: SubjectProperty, record: dict) -> Comp:
    """Build a comp, filling ``distance_miles`` from coordinates when absent."""
    record = dict(record)
    if "distance_miles" not in record:
        distance = miles_between(subject.facts, PropertyFacts(**record["facts"]))
        if distance is None:
            raise ValueError(
                f"comp {record.get('address', {}).get('street', '?')!r} has neither "
                "distance_miles nor coordinates"
            )
        record["distance_miles"] = round(distance, 2)
    return Comp(**record)


@dataclass(frozen=True)
class StaticCompSource:
    """In-memory comps, for tests and canned demos."""

    comps: list[Comp]

    def comps_for(self, subject: SubjectProperty) -> list[Comp]:
        return list(self.comps)


class JsonCompSource:
    """Comps from a JSON file: either a list or an object with a ``comps`` key."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def comps_for(self, subject: SubjectProperty) -> list[Comp]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        records = data["comps"] if isinstance(data, dict) else data
        return [comp_from_record(subject, record) for record in records]


def source_from_config(cfg: Config) -> CompSource:
    """Pick the configured comp source."""
    if cfg.comps_file:
        return JsonCompSource(cfg.comps_file)
    raise ValueError("no comp source configured: set ZPAVM_COMPS_FILE to a comps JSON file")
