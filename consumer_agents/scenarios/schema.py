"""Scenario YAML schema."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from consumer_agents.world.macro import MacroState


class ScenarioConfig(BaseModel):
    scenario_id: str
    start_date: date
    n_ticks: int = Field(default=90, ge=1)
    seed: int = 0
    personas_dir: str = "personas"
    world_dir: str = "world"
    notes: list[str] = Field(default_factory=list)

    macro: MacroState = Field(default_factory=MacroState)
    category_knobs: dict[str, float] = Field(default_factory=dict)
    scripted_events: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScenarioConfig:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
