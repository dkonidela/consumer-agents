"""Weekly reflection cycle.

Once per simulated week, the LLM produces 2–3 short reflections about
a persona's recent behavior. These get appended to the event log and
fed into future decision prompts so each persona's self-model carries
forward without re-reading the full event history.

Three modes (set via `mode=` in the constructor):

- "third_person" — model writes analytical observations about the
  persona ("Maya's behavior has become..."). The original/baseline.
  Tends to produce sociology-paper voice that crystallizes behavior
  into traits.

- "first_person" — model writes a private diary entry in the persona's
  voice ("I keep ending up at the same coffee shop..."). Same data,
  different framing. Hypothesis: first-person preserves uncertainty
  and openness that third-person analysis forecloses.

- "off" — skip the reflection step entirely. No LLM call. No
  reflections in the event log. No reflections in future decision
  prompts. Useful as an experimental control.

Without an Anthropic API key, `reflect()` returns []. Tests can
subclass and override.
"""

from __future__ import annotations

import os
from typing import Literal

import anthropic

from consumer_agents.personas.dna import Persona

ReflectionMode = Literal["third_person", "first_person", "off"]


REFLECT_TOOL = {
    "name": "emit_reflections",
    "description": "Emit 2–3 short reflections.",
    "input_schema": {
        "type": "object",
        "properties": {
            "observations": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
            }
        },
        "required": ["observations"],
    },
}


_THIRD_PERSON_SYSTEM = (
    "You are summarizing a synthetic consumer's recent week. "
    "Write 2–3 abstract observations about their state, behavior patterns, "
    "or trajectory. Be specific, not generic. Each observation: one sentence."
)

_FIRST_PERSON_SYSTEM = (
    "You are writing a private diary entry as this consumer. "
    "Write 2–3 short first-person reflections in their voice — things "
    "they noticed about their week, things they're considering, things "
    "they might do differently. Use \"I\", not \"they\". Sound like a "
    "personal journal entry, not a behavioral analysis. It's fine to be "
    "uncertain, ambivalent, or contradictory — diary entries usually are."
)


class ReflectionEngine:
    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        mode: ReflectionMode = "third_person",
    ):
        self.model = model
        self.mode = mode
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=key) if key else None

    def reflect(
        self,
        persona: Persona,
        recent_events: list[dict],
        prior_reflections: list[str],
    ) -> list[str]:
        if self.mode == "off":
            return []
        if self.client is None:
            return []

        system = (
            _FIRST_PERSON_SYSTEM if self.mode == "first_person" else _THIRD_PERSON_SYSTEM
        )
        user = self._build_prompt(persona, recent_events, prior_reflections)
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=system,
                tools=[REFLECT_TOOL],
                tool_choice={"type": "tool", "name": "emit_reflections"},
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[ReflectionEngine] LLM call failed ({exc}); no reflection.")
            return []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit_reflections":
                return list(block.input.get("observations", []))
        return []

    def _build_prompt(
        self,
        persona: Persona,
        recent_events: list[dict],
        prior_reflections: list[str],
    ) -> str:
        event_lines = [
            f"  - day {e.get('_tick_day_offset')}: {e.get('event_type')} {e.get('payload')}"
            for e in recent_events
        ] or ["  (none)"]
        prior_label = (
            "PRIOR DIARY ENTRIES:" if self.mode == "first_person" else "PRIOR REFLECTIONS:"
        )
        prior = "\n".join(f"  - {r}" for r in prior_reflections[-3:]) or "  (none)"
        closing = (
            "Write 2–3 first-person diary entries via the emit_reflections tool."
            if self.mode == "first_person"
            else "Emit 2–3 abstract observations via the emit_reflections tool."
        )
        return (
            f"CONSUMER: {persona.to_prompt()}\n\n"
            "LAST 7 DAYS OF EVENTS:\n" + "\n".join(event_lines) + "\n\n"
            f"{prior_label}\n{prior}\n\n"
            f"{closing}"
        )
