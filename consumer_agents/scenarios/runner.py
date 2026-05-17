"""Scenario runner — orchestrates one full simulation from a YAML config.

Engines (BehaviorEngine, ReflectionEngine, LifeEventEngine) can be
injected by callers — used by the smoke test to substitute a
deterministic fake for the LLM-backed BehaviorEngine. Production
callers leave them defaulted.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from consumer_agents.agents.behavior import BehaviorEngine
from consumer_agents.agents.reflection import ReflectionEngine
from consumer_agents.agents.scheduler import RunConfig, run_scheduler
from consumer_agents.personas.dna import load_personas
from consumer_agents.scenarios.schema import ScenarioConfig
from consumer_agents.world.catalog import load_catalog
from consumer_agents.world.life_events import LifeEventEngine, load_vocab


def run_scenario(
    scenario_path: str | Path,
    base_dir: str | Path | None = None,
    run_root: str | Path = "runs",
    model: str | None = None,
    behavior: BehaviorEngine | None = None,
    reflect: ReflectionEngine | None = None,
    life: LifeEventEngine | None = None,
) -> Path:
    """Run a scenario end-to-end and return the run directory path."""
    scenario_path = Path(scenario_path)
    config = ScenarioConfig.from_yaml(scenario_path)
    base = Path(base_dir) if base_dir else Path.cwd()

    run_id = f"{config.scenario_id}-{uuid.uuid4().hex[:8]}"
    run_dir = Path(run_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(scenario_path, run_dir / "scenario.yaml")
    (run_dir / "seed.txt").write_text(f"{config.seed}\n")

    personas = load_personas(base / config.personas_dir)
    catalog = load_catalog(base / config.world_dir)
    vocab = load_vocab(base / config.world_dir / "life_events_vocab.yaml")

    if behavior is None:
        behavior = BehaviorEngine(model=model or "claude-sonnet-4-6")
    if reflect is None:
        reflect = ReflectionEngine(model=model or "claude-sonnet-4-6")
    if life is None:
        life = LifeEventEngine(vocab=vocab)

    run_cfg = RunConfig(
        scenario_id=config.scenario_id,
        start_date=config.start_date,
        n_ticks=config.n_ticks,
        seed=config.seed,
        category_knobs=config.category_knobs,
        scripted_events=config.scripted_events,
        scenario_notes=config.notes,
        run_dir=run_dir,
    )
    run_scheduler(
        config=run_cfg,
        personas=personas,
        catalog=catalog,
        macro=config.macro,
        behavior=behavior,
        life=life,
        reflect=reflect,
    )
    return run_dir
