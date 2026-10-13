"""Hazard registry. Each analyzer takes (tmax series, years, low-quality years)."""

from app.hazards import heatwave

ANALYZERS = {"heatwave": heatwave.analyze}
