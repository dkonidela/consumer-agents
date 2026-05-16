"""Unit tests for DNA schema + persona loading."""

from __future__ import annotations

from pathlib import Path

from consumer_agents.personas.dna import load_persona, load_personas


def test_load_maya():
    repo = Path(__file__).resolve().parent.parent
    maya = load_persona(repo / "personas" / "maya.yaml")
    assert maya.id == "persona-maya-001"
    assert maya.identity.age == 28
    assert 0 <= maya.psychographics.big_five.O <= 1


def test_to_prompt_is_compact():
    repo = Path(__file__).resolve().parent.parent
    maya = load_persona(repo / "personas" / "maya.yaml")
    prompt = maya.to_prompt()
    assert "Maya" in prompt
    assert "Boston" in prompt
    assert len(prompt) < 500


def test_load_all_personas():
    repo = Path(__file__).resolve().parent.parent
    personas = load_personas(repo / "personas")
    assert len(personas) == 3
    names = {p.identity.name for p in personas}
    assert {"Maya Patel", "Raj Iyer", "Elena Morales"} == names
