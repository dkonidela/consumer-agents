"""Macro state — variables that affect every consumer's world."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MacroState(BaseModel):
    """Macro economic state. Mutated by scenario knobs."""

    inflation_rate: float = Field(default=0.03, description="Annual inflation, e.g., 0.03 = 3%")
    unemployment_rate: float = Field(default=0.04, description="Annual unemployment proxy")
    consumer_sentiment: float = Field(
        default=0.5, ge=0, le=1, description="0=pessimistic, 1=optimistic"
    )
    notes: list[str] = Field(default_factory=list, description="Scenario context for LLM prompts")

    def to_prompt(self) -> str:
        """Compact rendering for inclusion in BehaviorEngine prompts."""
        parts = [
            f"Inflation: {self.inflation_rate * 100:.1f}%",
            f"Unemployment: {self.unemployment_rate * 100:.1f}%",
            f"Consumer sentiment: {self.consumer_sentiment:.2f} (0=low, 1=high)",
        ]
        if self.notes:
            parts.append("Context: " + "; ".join(self.notes))
        return " | ".join(parts)
