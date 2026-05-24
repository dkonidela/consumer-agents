"""Scenario YAML schema."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from consumer_agents.world.macro import MacroState

ReflectionMode = Literal["third_person", "first_person", "off"]


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

    # Reflection mode controls how the weekly reflection step works:
    #   "third_person" — current/baseline: model writes analytical observations.
    #   "first_person" — model writes a diary entry in the persona's voice.
    #   "off"          — skip the reflection step entirely (no LLM call,
    #                    no reflections fed back into action prompts).
    reflection_mode: ReflectionMode = "third_person"

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScenarioConfig:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
