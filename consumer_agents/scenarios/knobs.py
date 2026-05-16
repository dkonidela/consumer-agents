"""Scenario knobs — small helpers for applying overrides.

v0 knobs:
  - category_knobs: per-category price multiplier offset (e.g., 0.20 = +20%)
  - macro overrides: bundled into the MacroState in the scenario YAML
  - scripted_events: pinned life events per day
  - notes: free-text prompt context

This module is intentionally thin. The knob values themselves live on
the ScenarioConfig; helpers here just centralize lookups.
"""

from __future__ import annotations


def category_price_knob(category_knobs: dict[str, float], category: str) -> float:
    """Return the multiplier offset for a category (default 0)."""
    return float(category_knobs.get(category, 0.0))
