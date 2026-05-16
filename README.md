# consumer-agents

> Open source agent simulation engine: synthetic consumers with structured DNA living in a retail world. Produces a queryable behavior datalake for counterfactual analysis.

**Status: v0, early.** Placeholder name. Spec lives at `docs/SPEC.md`.

## What it is

A small society of "digital humans" (3 in v0, scaling later) live day-to-day lives: working, browsing, buying, reacting to life events. Each consumer has structured DNA (Big Five personality, economics, life stage, preferences). A stateless `DecisionEngine` makes one LLM call (Anthropic) per consumer per day to decide what they do. Life events (scripted in v0 from the Holmes-Rahe vocabulary; LLM-driven in v1) mutate state over time. Output lands in Parquet + DuckDB, ready for analysis and articles.

## Why

A learning vehicle. Each subsystem (DNA, catalog, life events, datalake, scheduler, scenarios) is a distinct technical topic for deep technical articles. The architectural signature — *tiny structured seed + LLM at runtime + cache for reproducibility* — is the through-line.

## What it isn't

Not market research. Not predictive of real consumer behavior. With 3 LLM-driven personas, output is plausible but not empirically validated. Frame articles around technique, not predictions.

## v0 scope

- 3 hand-crafted personas (Maya, Raj, Elena)
- 3 categories (groceries, electronics, dining), 2 retailers (discount + mainstream)
- 10 life events from Holmes-Rahe (LLM-driven firing)
- Sync daily-tick scheduler
- 1 baseline scenario + 1 counterfactual (electronics +20%)
- Local Parquet + DuckDB datalake

## Install

```bash
pip install -e ".[dev]"
```

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
consumer-agents run examples/baseline.yaml
consumer-agents run examples/electronics_shock.yaml
```

Outputs land in `runs/<run_id>/events.parquet` and `runs/<run_id>/snapshots.parquet`.

## License

Apache-2.0.