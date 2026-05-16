"""Sync daily-tick scheduler.

For v0 (3 consumers, 90 days) the sync loop is enough. Async fan-out,
prompt caching, and the Batches API are deferred to v1; the
DecisionEngine adapter keeps that path additive, not a rewrite.

Per tick:
    for each consumer:
        1. fire any scripted life events for today
        2. credit payday / debit recurring expense
        3. ask the DecisionEngine what they do today; apply
        4. write daily-econ snapshot
    if it's the start of a new week:
        for each consumer:
            5. run the weekly reflection
            6. write weekly DNA snapshot

LLM-driven life events are v1. v0 fires only the scripted entries
from the scenario YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from consumer_agents.agents.decision import DecisionEngine
from consumer_agents.agents.loop import ConsumerRuntime, step
from consumer_agents.agents.reflection import ReflectionEngine
from consumer_agents.datalake.events import EventWriter
from consumer_agents.datalake.snapshots import SnapshotWriter
from consumer_agents.personas.dna import Persona
from consumer_agents.world.calendar import SimCalendar
from consumer_agents.world.catalog import Catalog
from consumer_agents.world.life_events import LifeEventEngine, apply_dna_diff
from consumer_agents.world.macro import MacroState


@dataclass
class RunConfig:
    scenario_id: str
    start_date: date
    n_ticks: int
    seed: int
    category_knobs: dict[str, float]
    scripted_events: list[dict]
    scenario_notes: list[str]
    run_dir: Path


def _scripted_for_day(scripted_events: list[dict], day_offset: int) -> list[dict]:
    return [e for e in scripted_events if int(e.get("day", -1)) == day_offset]


def run_scheduler(
    config: RunConfig,
    personas: list[Persona],
    catalog: Catalog,
    macro: MacroState,
    decision: DecisionEngine,
    life: LifeEventEngine,
    reflect: ReflectionEngine,
) -> None:
    events_writer = EventWriter(
        out_path=config.run_dir / "events.parquet",
        scenario_id=config.scenario_id,
    )
    snap_writer = SnapshotWriter(out_path=config.run_dir / "snapshots.parquet")

    runtimes: list[ConsumerRuntime] = [
        ConsumerRuntime(persona=p, cash_usd=p.economics.savings_usd) for p in personas
    ]

    calendar = SimCalendar(start_date=config.start_date, current_day=0)
    last_reflection_week = -1

    for _ in range(config.n_ticks):
        today = calendar.today
        scripted_today = _scripted_for_day(config.scripted_events, calendar.current_day)

        for rt in runtimes:
            # 1. Scripted life events for today.
            for fired in life.fire_scripted(rt.persona, scripted_today):
                rt.persona = apply_dna_diff(rt.persona, fired.dna_diff)
                payload = {
                    "event_id": fired.event_id,
                    "lcu": fired.lcu,
                    "narration": fired.narration,
                    "dna_diff": fired.dna_diff,
                    "source": fired.source,
                }
                events_writer.append(rt.persona.id, today, "life_event", payload)
                rt.record("life_event", payload, calendar.current_day)

            # 2-3. Daily step (cash flows + decision + actions).
            step(rt, decision, catalog, macro, calendar, events_writer, config.category_knobs)

            # 4. Daily economics snapshot.
            snap_writer.append_daily(rt.persona.id, today, rt.persona, rt.cash_usd)

        # 5-6. Weekly cadence: reflection + DNA snapshot.
        if calendar.week_index() != last_reflection_week and calendar.current_day > 0:
            last_reflection_week = calendar.week_index()
            for rt in runtimes:
                week_events = [
                    e
                    for e in rt.recent_events
                    if calendar.current_day - int(e.get("_tick_day_offset", 0)) <= 7
                ]
                observations = reflect.reflect(rt.persona, week_events, rt.reflections)
                if observations:
                    rt.reflections.extend(observations)
                    payload = {"observations": observations}
                    events_writer.append(rt.persona.id, today, "reflection", payload)
                    rt.record("reflection", payload, calendar.current_day)
                snap_writer.append_weekly_dna(rt.persona.id, today, rt.persona, rt.cash_usd)

        calendar.advance(1)

    events_writer.flush()
    snap_writer.flush()
