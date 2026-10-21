"""Environment-driven server config."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8010
    comps_file: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            transport=os.getenv("ZPAVM_TRANSPORT", "stdio"),
            host=os.getenv("ZPAVM_HOST", "127.0.0.1"),
            port=int(os.getenv("ZPAVM_PORT", "8010")),
            comps_file=os.getenv("ZPAVM_COMPS_FILE") or None,
        )
