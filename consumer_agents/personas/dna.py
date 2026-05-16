"""Persona DNA — structured state for one synthetic consumer."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class LifeStage(StrEnum):
    STUDENT = "student"
    SINGLE = "single"
    PARTNERED = "partnered"
    PARENT = "parent"
    RETIREE = "retiree"


class EmploymentStatus(StrEnum):
    EMPLOYED = "employed"
    UNEMPLOYED = "unemployed"
    STUDENT = "student"
    RETIRED = "retired"
    SELF_EMPLOYED = "self_employed"


class Location(BaseModel):
    city: str
    region: str


class Identity(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)
    gender: str
    location: Location


class Debt(BaseModel):
    student_loan_usd: float = 0
    credit_card_usd: float = 0
    mortgage_usd: float = 0
    other_usd: float = 0

    @property
    def total(self) -> float:
        return self.student_loan_usd + self.credit_card_usd + self.mortgage_usd + self.other_usd


class RecurringExpenses(BaseModel):
    rent: float = 0
    utilities: float = 0
    subscriptions: float = 0
    transit: float = 0
    insurance: float = 0
    childcare: float = 0
    other: float = 0

    @property
    def monthly_total(self) -> float:
        return (
            self.rent
            + self.utilities
            + self.subscriptions
            + self.transit
            + self.insurance
            + self.childcare
            + self.other
        )


class Economics(BaseModel):
    occupation: str
    employment_status: EmploymentStatus
    monthly_income_usd: float = Field(ge=0)
    savings_usd: float
    debt: Debt = Field(default_factory=Debt)
    recurring_expenses_usd: RecurringExpenses = Field(default_factory=RecurringExpenses)


class BigFive(BaseModel):
    """Each trait scored 0..1. Stable for the run."""

    O: float = Field(ge=0, le=1)
    C: float = Field(ge=0, le=1)
    E: float = Field(ge=0, le=1)
    A: float = Field(ge=0, le=1)
    N: float = Field(ge=0, le=1)


class Values(BaseModel):
    """What the consumer cares about when choosing. Each 0..1."""

    price: float = Field(ge=0, le=1)
    quality: float = Field(ge=0, le=1)
    brand: float = Field(ge=0, le=1)
    eco: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)


class Psychographics(BaseModel):
    big_five: BigFive
    values: Values


class Household(BaseModel):
    composition: str  # alone | roommates | couple | family | etc.
    size: int = Field(ge=1)


class LifeStageBlock(BaseModel):
    stage: LifeStage
    household: Household
    children: int = Field(ge=0, default=0)


class Preferences(BaseModel):
    category_propensity: dict[str, float] = Field(default_factory=dict)
    channel: str = "online_first"  # online_first | in_store | mixed
    price_sensitivity: float = Field(ge=0, le=1, default=0.5)


class Persona(BaseModel):
    """Top-level DNA record for one consumer.

    Versioned via `dna_version` so we can evolve the schema without
    breaking older runs/snapshots.
    """

    id: str
    dna_version: int = 1
    identity: Identity
    economics: Economics
    psychographics: Psychographics
    life_stage: LifeStageBlock
    preferences: Preferences = Field(default_factory=Preferences)

    @field_validator("preferences", mode="before")
    @classmethod
    def _default_prefs(cls, v: Any) -> Any:
        return v or {}

    def to_prompt(self) -> str:
        """Compact natural-language rendering for the DecisionEngine system prompt."""
        bf = self.psychographics.big_five
        v = self.psychographics.values
        traits = []
        if bf.O >= 0.7:
            traits.append("highly open to new things")
        elif bf.O <= 0.3:
            traits.append("traditional, prefers familiar")
        if bf.C >= 0.7:
            traits.append("conscientious and planned")
        elif bf.C <= 0.3:
            traits.append("spontaneous")
        if bf.E >= 0.7:
            traits.append("extraverted")
        elif bf.E <= 0.3:
            traits.append("introverted")
        if bf.N >= 0.7:
            traits.append("emotionally reactive")
        if v.price >= 0.7:
            traits.append("very price-sensitive")
        if v.eco >= 0.7:
            traits.append("eco-conscious")
        if v.brand >= 0.7:
            traits.append("brand-loyal")
        if v.novelty >= 0.7:
            traits.append("drawn to novelty")
        trait_str = ", ".join(traits) if traits else "balanced temperament"

        econ = self.economics
        debt_total = econ.debt.total
        debt_str = f", ${debt_total:,.0f} in debt" if debt_total > 0 else ""

        return (
            f"{self.identity.name}, {self.identity.age}, "
            f"{econ.occupation} in {self.identity.location.city}. "
            f"Earns ${econ.monthly_income_usd:,.0f}/mo, "
            f"${econ.savings_usd:,.0f} savings{debt_str}. "
            f"{trait_str.capitalize()}. "
            f"{self.life_stage.stage.value.capitalize()} stage, "
            f"household of {self.life_stage.household.size} "
            f"({self.life_stage.household.composition})."
        )


def load_persona(path: str | Path) -> Persona:
    """Load a single persona from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return Persona(**data)


def load_personas(dir_path: str | Path) -> list[Persona]:
    """Load every .yaml file in a directory as a Persona."""
    p = Path(dir_path)
    personas = [load_persona(f) for f in sorted(p.glob("*.yaml"))]
    return personas
