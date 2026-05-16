"""Life-Event engine — scripted-only in v0.

Scripted events are pinned to specific days and consumers in the
scenario YAML. They fire deterministically every time the scenario
runs with the same seed.

v0 uses scripted-only firing. LLM-driven life events (where the LLM
decides, weekly per consumer, whether anything happened based on
the persona's situation) are deferred to v1. The Holmes-Rahe
`life_events_vocab.yaml` still ships in v0 so v1 can plug LLM
firing back in without changes to scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from consumer_agents.personas.dna import Persona


class LifeEventVocab(BaseModel):
    id: str
    lcu: int
    group: str


def load_vocab(path: str | Path) -> list[LifeEventVocab]:
    with open(path) as f:
        rows = yaml.safe_load(f) or []
    return [LifeEventVocab(**r) for r in rows]


@dataclass
class FiredEvent:
    event_id: str
    lcu: int
    narration: str
    dna_diff: dict[str, Any]
    source: str  # 'scripted' (v0) | 'llm' (v1)


def apply_dna_diff(persona: Persona, diff: dict[str, Any]) -> Persona:
    """Apply a dotted-path diff and return a new Persona instance."""
    data = persona.model_dump()
    for path, value in diff.items():
        keys = path.split(".")
        d = data
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
    return Persona(**data)


class LifeEventEngine:
    """v0: scripted firing only. One instance serves all consumers."""

    def __init__(self, vocab: list[LifeEventVocab]):
        self.vocab = vocab

    def fire_scripted(
        self,
        persona: Persona,
        scripted_today: list[dict],
    ) -> list[FiredEvent]:
        fired: list[FiredEvent] = []
        for entry in scripted_today:
            if entry.get("agent_id") and entry["agent_id"] != persona.id:
                continue
            ev_id = entry["event_id"]
            lcu = next((v.lcu for v in self.vocab if v.id == ev_id), 0)
            fired.append(
                FiredEvent(
                    event_id=ev_id,
                    lcu=lcu,
                    narration=entry.get("narration", f"Scripted: {ev_id}"),
                    dna_diff=entry.get("dna_diff", {}),
                    source="scripted",
                )
            )
        return fired
