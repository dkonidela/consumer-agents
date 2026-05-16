"""Weekly reflection cycle (Park et al., 'Generative Agents', 2023).

Once per simulated week, the LLM produces 2–3 abstract observations
about a persona's recent behavior. These reflections feed back into
future decision prompts so each persona's self-model carries forward
without re-reading the full event history.

Without an Anthropic API key, `reflect()` returns []. Tests can
subclass and override.
"""

from __future__ import annotations

import os

import anthropic

from consumer_agents.personas.dna import Persona

REFLECT_TOOL = {
    "name": "emit_reflections",
    "description": "Emit 2–3 abstract observations about the consumer's current state or behavior.",
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


class ReflectionEngine:
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        self.model = model
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=key) if key else None

    def reflect(
        self,
        persona: Persona,
        recent_events: list[dict],
        prior_reflections: list[str],
    ) -> list[str]:
        if self.client is None:
            return []
        system = (
            "You are summarizing a synthetic consumer's recent week. "
            "Write 2–3 abstract observations about their state, behavior patterns, "
            "or trajectory. Be specific, not generic. Each observation: one sentence."
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
        prior = "\n".join(f"  - {r}" for r in prior_reflections[-3:]) or "  (none)"
        return (
            f"CONSUMER: {persona.to_prompt()}\n\n"
            "LAST 7 DAYS OF EVENTS:\n" + "\n".join(event_lines) + "\n\n"
            f"PRIOR REFLECTIONS:\n{prior}\n\n"
            "Emit 2–3 abstract observations via the emit_reflections tool."
        )
