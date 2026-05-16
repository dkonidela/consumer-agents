"""DecisionEngine — one LLM call per consumer per day.

A stateless engine. The same instance serves every consumer. Each
`decide()` call sends the persona's DNA, recent memory, reflections,
catalog, macro state, and scenario knobs to the LLM, which returns a
structured list of actions via the `emit_actions` tool.

When no ANTHROPIC_API_KEY is configured, `decide()` returns an empty
action list. Tests inject a `FakeDecisionEngine` subclass instead of
relying on a production fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import anthropic

from consumer_agents.personas.dna import Persona
from consumer_agents.world.calendar import SimCalendar
from consumer_agents.world.catalog import Catalog
from consumer_agents.world.macro import MacroState


@dataclass
class Action:
    event_type: str
    payload: dict[str, Any]


DEFAULT_MODEL = "claude-sonnet-4-6"

EMIT_ACTIONS_TOOL = {
    "name": "emit_actions",
    "description": (
        "Emit the consumer's actions for today. Return a list of actions. "
        "Most days have a few actions or none at all. Valid event_type "
        "values: view, cart_add, purchase, abandon."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "enum": ["view", "cart_add", "purchase", "abandon"],
                        },
                        "payload": {"type": "object"},
                    },
                    "required": ["event_type", "payload"],
                },
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this set of actions",
            },
        },
        "required": ["actions"],
    },
}


class DecisionEngine:
    """One LLM call per consumer per tick. No rule path, no stub."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=key) if key else None

    def decide(
        self,
        persona: Persona,
        catalog: Catalog,
        macro: MacroState,
        calendar: SimCalendar,
        recent_events: list[dict],
        reflections: list[str],
        cash_usd: float,
        category_knobs: dict[str, float] | None = None,
    ) -> list[Action]:
        if self.client is None:
            return []
        category_knobs = category_knobs or {}
        system = self._build_system_prompt(persona, macro)
        user = self._build_user_prompt(
            persona, catalog, calendar, recent_events, reflections, cash_usd, category_knobs
        )
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                tools=[EMIT_ACTIONS_TOOL],
                tool_choice={"type": "tool", "name": "emit_actions"},
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[DecisionEngine] LLM call failed ({exc}); no actions today.")
            return []

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit_actions":
                actions_raw = block.input.get("actions", [])
                return [
                    Action(event_type=a["event_type"], payload=a["payload"])
                    for a in actions_raw
                ]
        return []

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_system_prompt(self, persona: Persona, macro: MacroState) -> str:
        return (
            "You are simulating one synthetic consumer's behavior for a single day in a "
            "small retail world. Stay in character: their personality and economic "
            "situation should drive every choice. You must call the `emit_actions` tool "
            "with a list of structured actions for TODAY ONLY. Be realistic — not every "
            "day is a shopping day. Empty action lists are fine.\n\n"
            f"CONSUMER: {persona.to_prompt()}\n\n"
            f"WORLD MACRO STATE: {macro.to_prompt()}"
        )

    def _build_user_prompt(
        self,
        persona: Persona,
        catalog: Catalog,
        calendar: SimCalendar,
        recent_events: list[dict],
        reflections: list[str],
        cash_usd: float,
        category_knobs: dict[str, float],
    ) -> str:
        sku_lines: list[str] = []
        for cat in catalog.categories:
            for sku in catalog.skus_by_category(cat):
                price = sku.base_price_usd * (1 + category_knobs.get(cat, 0))
                sku_lines.append(
                    f"  - {sku.id} | {sku.name} | {cat} | {sku.brand} | "
                    f"{sku.quality_tier} | ~${price:.2f}"
                )

        retailer_lines = [
            f"  - {r.id} | {r.name} | {r.positioning} | price_mult={r.price_mult} | "
            f"carries={','.join(r.assortment)}"
            for r in catalog.retailers
        ]

        recent_str = "\n".join(
            f"  - day {e.get('_tick_day_offset')}: {e.get('event_type')} {e.get('payload')}"
            for e in recent_events[-15:]
        ) or "  (none)"

        reflections_str = "\n".join(f"  - {r}" for r in reflections[-3:]) or "  (none)"

        knob_str = (
            ", ".join(f"{k}: {v * 100:+.0f}%" for k, v in category_knobs.items())
            or "(none)"
        )

        dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][calendar.day_of_week()]
        return (
            f"Today is day {calendar.current_day} of the simulation "
            f"({calendar.today.isoformat()}, {dow}).\n"
            f"Cash on hand: ${cash_usd:,.2f}\n"
            f"Scenario price adjustments (relative to baseline): {knob_str}\n\n"
            f"CATALOG (price shown includes any scenario adjustment, before retailer multiplier):\n"
            + "\n".join(sku_lines)
            + "\n\nRETAILERS:\n"
            + "\n".join(retailer_lines)
            + f"\n\nRECENT EVENTS (last 15):\n{recent_str}\n\n"
            f"RECENT REFLECTIONS:\n{reflections_str}\n\n"
            "Decide what (if anything) this consumer does today. Possible event types:\n"
            "  - view: looked at a category or specific SKU. "
            "payload: {category, sku_id?, retailer?, price_shown?}\n"
            "  - cart_add: added an item to today's cart. "
            "payload: {sku_id, qty, retailer, unit_price_usd}\n"
            "  - purchase: checked out. "
            "payload: {cart_id, items: [{sku_id, qty}], total_usd, retailer}\n"
            "  - abandon: left a cart unpurchased. "
            "payload: {cart_id, reason}\n\n"
            "Carts do not persist across days; finish or abandon today. Be realistic "
            "about quantities, affordability, and category-by-category needs."
        )
