"""End-to-end smoke test with an injected FakeDecisionEngine.

Runs without an ANTHROPIC_API_KEY. The real DecisionEngine returns []
when no key is set; tests inject a small fake that emits a
deterministic action sequence so the rest of the pipeline can be
verified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from consumer_agents.agents.decision import Action, DecisionEngine
from consumer_agents.datalake.queries import open_run
from consumer_agents.scenarios.runner import run_scenario


class FakeDecisionEngine(DecisionEngine):
    """Deterministic engine: Tue/Sat = grocery purchase; Sun = dining outing."""

    def __init__(self):
        # Bypass real __init__ — no API client needed.
        self.model = "fake"
        self.client = None

    def decide(self, persona, catalog, macro, calendar, recent_events, reflections, cash_usd, category_knobs=None):
        dow = calendar.day_of_week()
        if dow in {1, 5}:  # Tue, Sat
            sku = catalog.skus_by_category("groceries")[0]
            retailer = catalog.retailers_for_category("groceries")[0]
            price = sku.base_price_usd * retailer.price_mult
            return [
                Action(
                    "view",
                    {
                        "category": "groceries",
                        "sku_id": sku.id,
                        "retailer": retailer.id,
                        "price_shown": round(price, 2),
                    },
                ),
                Action(
                    "cart_add",
                    {"sku_id": sku.id, "qty": 1, "retailer": retailer.id, "unit_price_usd": round(price, 2)},
                ),
                Action(
                    "purchase",
                    {
                        "cart_id": f"cart-{persona.id[-6:]}-d{calendar.current_day}",
                        "items": [{"sku_id": sku.id, "qty": 1}],
                        "total_usd": round(price, 2),
                        "retailer": retailer.id,
                    },
                ),
            ]
        if dow == 6:  # Sun
            sku = catalog.skus_by_category("dining")[0]
            retailer = catalog.retailers_for_category("dining")[0]
            price = sku.base_price_usd * retailer.price_mult
            return [
                Action(
                    "view",
                    {
                        "category": "dining",
                        "sku_id": sku.id,
                        "retailer": retailer.id,
                        "price_shown": round(price, 2),
                    },
                ),
                Action(
                    "purchase",
                    {
                        "cart_id": f"cart-{persona.id[-6:]}-dine-d{calendar.current_day}",
                        "items": [{"sku_id": sku.id, "qty": 1}],
                        "total_usd": round(price, 2),
                        "retailer": retailer.id,
                    },
                ),
            ]
        return []


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def smoke_scenario(tmp_path: Path, repo_root: Path) -> Path:
    scenario_path = tmp_path / "smoke.yaml"
    scenario_path.write_text(
        f"""scenario_id: smoke
start_date: 2026-01-01
n_ticks: 14
seed: 0

personas_dir: {repo_root}/personas
world_dir: {repo_root}/world

notes:
  - smoke test

macro:
  inflation_rate: 0.03
  unemployment_rate: 0.04
  consumer_sentiment: 0.5

category_knobs: {{}}

scripted_events: []
"""
    )
    return scenario_path


def test_smoke_run(smoke_scenario: Path, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    run_dir = run_scenario(
        scenario_path=smoke_scenario,
        run_root=tmp_path / "runs",
        decision=FakeDecisionEngine(),
    )
    assert run_dir.exists()
    assert (run_dir / "events.parquet").exists()
    assert (run_dir / "snapshots.parquet").exists()

    con = open_run(run_dir)

    event_total = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert event_total > 0

    snap_total = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    assert snap_total > 0

    # Every persona should have produced events.
    by_agent = con.execute("SELECT agent_id, COUNT(*) FROM events GROUP BY 1").fetchall()
    assert len(by_agent) == 3
    for _, n in by_agent:
        assert n > 0

    # Fake engine emits purchases on Tue/Sat/Sun (≥6 per agent over 14 days).
    purchase_total = con.execute("SELECT COUNT(*) FROM v_purchases").fetchone()[0]
    assert purchase_total >= 18


def test_reproducibility(smoke_scenario: Path, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r1 = run_scenario(
        scenario_path=smoke_scenario, run_root=tmp_path / "r1", decision=FakeDecisionEngine()
    )
    r2 = run_scenario(
        scenario_path=smoke_scenario, run_root=tmp_path / "r2", decision=FakeDecisionEngine()
    )
    con1 = open_run(r1)
    con2 = open_run(r2)
    c1 = con1.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    c2 = con2.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert c1 == c2


def test_decision_engine_no_key_returns_empty(monkeypatch):
    """Without an API key, the real DecisionEngine returns [] — no fallback stub."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    engine = DecisionEngine()
    from datetime import date

    from consumer_agents.personas.dna import load_persona
    from consumer_agents.world.calendar import SimCalendar
    from consumer_agents.world.catalog import load_catalog
    from consumer_agents.world.macro import MacroState

    repo = Path(__file__).resolve().parent.parent
    persona = load_persona(repo / "personas" / "maya.yaml")
    catalog = load_catalog(repo / "world")
    cal = SimCalendar(start_date=date(2026, 1, 1), current_day=5)
    actions = engine.decide(persona, catalog, MacroState(), cal, [], [], 1000.0)
    assert actions == []
