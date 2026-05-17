"""Per-consumer step function (sense → think → act → log).

Pure state-mutation step. Called once per consumer per tick by the
scheduler. No looping logic here — that lives in scheduler.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from consumer_agents.agents.behavior import Action, BehaviorEngine
from consumer_agents.datalake.events import EventWriter
from consumer_agents.personas.dna import Persona
from consumer_agents.world.calendar import SimCalendar
from consumer_agents.world.catalog import Catalog
from consumer_agents.world.macro import MacroState


@dataclass
class ConsumerRuntime:
    """Per-consumer mutable state held by the scheduler across ticks."""

    persona: Persona
    cash_usd: float = 0.0
    recent_events: list[dict] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)

    def record(self, event_type: str, payload: dict[str, Any], tick_day_offset: int) -> None:
        self.recent_events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "_tick_day_offset": tick_day_offset,
            }
        )
        # Cap memory to the last ~30 events for routing decisions.
        if len(self.recent_events) > 60:
            self.recent_events = self.recent_events[-60:]


def emit_payday_and_expenses(
    rt: ConsumerRuntime,
    calendar: SimCalendar,
    writer: EventWriter,
) -> None:
    """Credit bi-monthly income on paydays; debit full recurring expenses
    once per month on the 1st. Cleaner event log than daily slicing and
    more realistic — rent isn't actually debited in 1/30 chunks."""
    persona = rt.persona
    today = calendar.today

    if calendar.is_payday() and persona.economics.monthly_income_usd > 0:
        amount = persona.economics.monthly_income_usd / 2  # bi-monthly
        rt.cash_usd += amount
        payload = {"amount_usd": round(amount, 2), "source": "payday"}
        writer.append(persona.id, today, "income", payload)
        rt.record("income", payload, calendar.current_day)

    monthly_expense = persona.economics.recurring_expenses_usd.monthly_total
    if calendar.is_first_of_month() and monthly_expense > 0:
        rt.cash_usd -= monthly_expense
        payload = {"amount_usd": round(monthly_expense, 2), "category": "recurring"}
        writer.append(persona.id, today, "expense", payload)
        rt.record("expense", payload, calendar.current_day)


def apply_actions(
    rt: ConsumerRuntime,
    actions: list[Action],
    tick_day: date,
    tick_day_offset: int,
    writer: EventWriter,
) -> None:
    """Emit events to the datalake and adjust cash for purchases."""
    for action in actions:
        writer.append(rt.persona.id, tick_day, action.event_type, action.payload)
        rt.record(action.event_type, action.payload, tick_day_offset)
        if action.event_type == "purchase":
            total = float(action.payload.get("total_usd", 0))
            rt.cash_usd -= total
        elif action.event_type == "return":
            total = float(action.payload.get("refund_usd", 0))
            rt.cash_usd += total


def step(
    rt: ConsumerRuntime,
    engine: BehaviorEngine,
    catalog: Catalog,
    macro: MacroState,
    calendar: SimCalendar,
    writer: EventWriter,
    category_knobs: dict[str, float] | None = None,
) -> None:
    """One consumer's day: cash flows + decisions + logging."""
    emit_payday_and_expenses(rt, calendar, writer)
    actions = engine.simulate(
        persona=rt.persona,
        catalog=catalog,
        macro=macro,
        calendar=calendar,
        recent_events=rt.recent_events,
        reflections=rt.reflections,
        cash_usd=rt.cash_usd,
        category_knobs=category_knobs or {},
    )
    apply_actions(rt, actions, calendar.today, calendar.current_day, writer)
