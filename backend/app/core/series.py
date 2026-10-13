from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class DailySeries:
    """Daily values starting at `start`; list index = day offset. None = missing."""

    start: date
    tmax: list[float | None]
    precip: list[float | None]
    sources: list[str]

    @property
    def end(self) -> date:
        return self.start + timedelta(days=len(self.tmax) - 1)
