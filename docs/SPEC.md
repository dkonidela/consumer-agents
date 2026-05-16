# consumer-agents — System Spec

A reading guide to the codebase. This document explains how the pieces
fit together, where each concept lives in the source tree, and how to
extend the system without breaking it.

Companion to the README. For the original design discussion + rationale
behind each decision, see `~/.claude/plans/we-are-starting-an-cosmic-simon.md`.

---

## 1. What the system does

Simulates a small society of synthetic consumers (3 in v0, designed to
scale to 100s–1000s) who live day-to-day lives in a small retail world:
they earn paychecks, pay bills, shop for groceries and electronics and
dining, and experience life events (layoffs, marriages, illnesses) that
shift their behavior over time.

Each simulated tick = one day. The output is a Parquet-based behavior
datalake — `events.parquet` and `snapshots.parquet` — queryable via
DuckDB and ready for notebooks or articles.

The system is **LLM-native**: the decision-making and weekly reflections
run through an LLM (Anthropic) at runtime rather than from hardcoded
rule sets. Without an `ANTHROPIC_API_KEY`, the engines return empty
results; tests inject a deterministic `FakeDecisionEngine` to exercise
the pipeline end-to-end without a key.

**v0 keeps the engine surface narrow.** One LLM call per consumer per
day for decisions; one LLM call per consumer per week for reflections.
Life events in v0 fire only from the scripted entries in the scenario
YAML — no stochastic / LLM-driven life-event firing. (That path is
specified for v1 and the Holmes-Rahe vocabulary ships now so it can be
added without scenario-format changes.)

---

## 2. Architecture at a glance

```
┌────────────────────────────────────────────────────────────────────┐
│                         Scenario Runner                             │
│   consumer_agents/scenarios/runner.py                               │
│   Loads YAML → builds World + Personas + Engines → drives Scheduler │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                            Scheduler                                │
│   consumer_agents/agents/scheduler.py                               │
│                                                                     │
│   for each tick (day):                                              │
│       for each consumer:                                            │
│           1. fire scripted life events for today                    │
│           2. step()  (cash flows + decision + actions)              │
│           3. write daily-econ snapshot                              │
│                                                                     │
│       if start of new week:                                         │
│           for each consumer:                                        │
│               4. reflection cycle  (weekly LLM call)                │
│               5. write weekly DNA snapshot                          │
└────────────────────────────────────────────────────────────────────┘
        │                  │                       │
        ▼                  ▼                       ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────────────────┐
│ Persona DNA  │  │ World           │  │ LLM-backed Engines       │
│ (data)       │  │ Calendar /      │  │ DecisionEngine           │
│              │  │ Catalog /       │  │ ReflectionEngine         │
│              │  │ MacroState      │  │ LifeEventEngine          │
└──────────────┘  └─────────────────┘  └──────────────────────────┘
                                                │
                                                ▼
                                ┌────────────────────────────────┐
                                │       Behavior Datalake        │
                                │  runs/<run_id>/                │
                                │     events.parquet             │
                                │     snapshots.parquet          │
                                │     scenario.yaml (immutable)  │
                                │     seed.txt                   │
                                │  + DuckDB typed views          │
                                └────────────────────────────────┘
```

The scheduler is **synchronous** in v0. The `DecisionEngine` adapter
keeps the async / Batches API / prompt-caching path additive for v1 —
not a rewrite. See `consumer_agents/agents/scheduler.py`.

**One stateless `DecisionEngine` serves every consumer.** A consumer is
data (DNA + memory + event history), not a process. This is what makes
the same architecture cover 3 consumers and 1,000 consumers without
re-engineering.

---

## 3. Repo layout

```
consumer-agents/
├── pyproject.toml            # deps, ruff config, pytest config, CLI entrypoint
├── README.md
├── LICENSE                   # Apache-2.0
├── docs/
│   └── SPEC.md               # this file
├── consumer_agents/          # the Python package
│   ├── personas/
│   │   └── dna.py            # Pydantic DNA schema + Persona.to_prompt()
│   ├── world/
│   │   ├── calendar.py       # SimCalendar: day-tick, paydays, weekends
│   │   ├── macro.py          # MacroState: inflation, unemployment, sentiment
│   │   ├── catalog.py        # SKU, Retailer, pricing formula, loader
│   │   ├── catalog_loader.py # Open Food Facts loader stub (v1)
│   │   └── life_events.py    # LifeEventEngine + dotted-path DNA diffs
│   ├── agents/
│   │   ├── decision.py       # DecisionEngine — single LLM call per day
│   │   ├── reflection.py     # Weekly reflections (Park et al., 2023)
│   │   ├── loop.py           # Per-consumer daily step()
│   │   └── scheduler.py      # The outer for-each-tick loop
│   ├── scenarios/
│   │   ├── schema.py         # ScenarioConfig (Pydantic)
│   │   ├── knobs.py          # Knob helpers (thin)
│   │   └── runner.py         # Loads scenario YAML → drives full run
│   ├── datalake/
│   │   ├── events.py         # EventWriter: append-only Parquet
│   │   ├── snapshots.py      # SnapshotWriter: daily econ + weekly DNA
│   │   └── queries.py        # DuckDB views + open_run(run_dir)
│   └── cli.py                # typer CLI: run / analyze / init
├── personas/                 # YAML seeds for the 3 v0 archetypes
│   ├── maya.yaml             # 28, grad student, urban, price-sensitive
│   ├── raj.yaml              # 41, suburban dad, mid-high income, brand-loyal
│   └── elena.yaml            # 67, retiree, fixed income, quality-focused
├── world/                    # YAML seeds for the v0 world
│   ├── retailers.yaml        # 2 retailers (discount + mainstream)
│   ├── life_events_vocab.yaml         # 10 Holmes-Rahe events
│   ├── catalog_seed_groceries.yaml    # 25 SKUs
│   ├── catalog_seed_electronics.yaml  # 15 SKUs
│   └── catalog_seed_dining.yaml       # 15 SKUs
├── examples/                 # scenario YAMLs
│   ├── baseline.yaml         # 3 agents × 90 days, no perturbations
│   └── electronics_shock.yaml # electronics +20%, scripted layoff
├── notebooks/                # analysis (one notebook in v0)
├── tests/                    # pytest
│   ├── test_dna.py           # schema + persona loading
│   ├── test_catalog.py       # catalog + pricing formula
│   └── test_smoke.py         # end-to-end smoke
└── runs/                     # output directory (gitignored)
    └── <scenario>-<hash>/
        ├── events.parquet
        ├── snapshots.parquet
        ├── scenario.yaml
        └── seed.txt
```

---

## 4. A day in the life of Maya — call-path walkthrough

This is the single most useful section for understanding the code.
Trace one simulated day from CLI invocation to Parquet write.

**Invocation**
```
consumer-agents run examples/baseline.yaml
```

1. `consumer_agents/cli.py` → `run()` calls
   `consumer_agents/scenarios/runner.py:run_scenario()`.

2. `run_scenario()`
   - Parses YAML into `ScenarioConfig` (`scenarios/schema.py`).
   - Loads personas from `personas/*.yaml` (`personas/dna.py:load_personas`).
   - Loads catalog SKUs + retailers from `world/*.yaml`
     (`world/catalog.py:load_catalog`).
   - Loads the 10-event Holmes-Rahe vocabulary
     (`world/life_events.py:load_vocab`).
   - Constructs the engines: `DecisionEngine`, `ReflectionEngine`,
     `LifeEventEngine`.
   - Builds a `RunConfig` and calls `agents/scheduler.py:run_scheduler()`.

3. `run_scheduler()` opens an `EventWriter` and a `SnapshotWriter`, then
   loops `for _ in range(n_ticks)`:

   **For each consumer on each day:**

   a. **Scripted life events.** If today has a scripted entry for this
      agent in `scenario.scripted_events`, fire it via
      `LifeEventEngine.fire_scripted()`. The dotted-path `dna_diff` is
      applied with `apply_dna_diff()` (mutating e.g.
      `economics.employment_status` from `"student"` to `"unemployed"`).
      A `life_event` row is appended.

   b. **Daily step** (`agents/loop.py:step`):
      - **emit_payday_and_expenses()**: on the 15th and last day of the
        month, credit half the monthly income to `cash_usd` and emit an
        `income` event. Every day, debit 1/30 of monthly recurring
        expenses and emit an `expense` event.
      - **decide()** (`agents/decision.py:DecisionEngine.decide`):
        One LLM call. Returns a list of `Action`s. With no API key it
        returns `[]`; tests inject a `FakeDecisionEngine` subclass to
        emit deterministic actions instead.
      - **apply_actions()**: emit each `Action` to the EventWriter and
        deduct cash on `purchase`.

   c. **Daily snapshot** (`datalake/snapshots.py:append_daily`):
      one row in `snapshots.parquet` with cash/savings/debt/employment.

   **End of a simulated week** (every 7 days):

   d. **Reflection** (`agents/reflection.py:ReflectionEngine.reflect`):
      One LLM call that produces 2–3 abstract observations about the
      persona's week. Stored in `runtime.reflections` and emitted as a
      `reflection` event. These are passed to future `decide()` calls
      so the persona's self-model carries forward.

   e. **Weekly DNA snapshot**: full persona blob serialized to JSON in
      `snapshots.parquet`. State at any tick is reconstructable from
      the nearest weekly snapshot + intervening events.

4. `EventWriter.flush()` and `SnapshotWriter.flush()` write Parquet.
   `runs/<run_id>/scenario.yaml` and `seed.txt` capture provenance.

**Analysis**
```
consumer-agents analyze runs/<run_id>
```
opens DuckDB views over the Parquet files (`datalake/queries.py`) and
prints event-count and per-agent-spend tables.

---

## 5. Key concepts

### 5.1 Persona DNA (`personas/dna.py`)

A `Persona` is structured state for one synthetic consumer. Six logical
blocks, all Pydantic models:

- **Identity**: name, age, gender, location.
- **Economics**: occupation, employment status, monthly income, savings,
  debt breakdown, recurring expenses breakdown. All amounts USD.
- **Psychographics**: Big Five personality (OCEAN, each 0..1) +
  Values (price/quality/brand/eco/novelty, each 0..1).
- **Life stage**: enum (student/single/partnered/parent/retiree) +
  household composition + children count.
- **Preferences**: per-category propensity dict, channel, price
  sensitivity.

`dna_version: int` lets the schema evolve without breaking older
snapshots. The whole record can be serialized to JSON (for weekly
snapshots) and reloaded from YAML at startup.

**`Persona.to_prompt()`** is critical: it produces a compact natural-
language rendering (~3 sentences) for inclusion in LLM prompts. Raw
JSON is verbose and noisy; the prompt rendering is what makes
prompt-caching effective and tokens cheap.

DNA is **mutable** through life events only. Big Five and values never
change within a run. Cash flows mutate every tick. The
`apply_dna_diff()` helper in `world/life_events.py` handles dotted-path
mutations like `economics.employment_status: "unemployed"`.

Archetypes ship in `personas/*.yaml`. v0 has 3, deliberately spread
across age, life stage, income, and personality so behavior is legible
in articles. A procedural generator is planned for v1 (when we need
100s of agents).

### 5.2 DecisionEngine (`agents/decision.py`)

One stateless instance serves every consumer. Per-tick flow is a
single LLM call:

```
decide(persona, catalog, macro, calendar,
       recent_events, reflections, cash, knobs)
    │
    ├─► api_key present → LLM call (emit_actions tool) → list[Action]
    │
    └─► no api_key      → []   (tests inject FakeDecisionEngine)
```

The LLM is forced via `tool_choice` to emit a list of
`{event_type, payload}` actions. Failure (network, parse error, rate
limit) returns `[]` so a single bad call never poisons a run. Tests
inject a `FakeDecisionEngine` subclass that overrides `decide()` to
emit deterministic actions for the no-key path.

Output is a list of `Action(event_type, payload)`. The loop layer
turns these into events written to Parquet and applies cash changes.

The routine/non-routine routing from the original design (to cut LLM
cost on idle days) was dropped in the simplification pass — at v0
scale the savings don't earn the complexity. It's a clean v1 addition
when scaling to 100s of consumers.

### 5.3 Life events (`world/life_events.py`)

**v0: scripted-only.** Events are pinned to specific days and
consumers in the scenario YAML. They fire deterministically every
time the scenario runs with the same seed.

`scenario.scripted_events` is a list of:
```yaml
- day: 45
  agent_id: persona-maya-001
  event_id: fired_from_work
  narration: "Maya's grant runs dry..."
  dna_diff:
    economics.employment_status: unemployed
    economics.monthly_income_usd: 0
```

The `dna_diff` is applied via `apply_dna_diff()` which understands
dotted paths into the Persona model. The fired event is emitted as a
`life_event` row in `events.parquet` with the narration and diff in
the payload for analytics.

**v1: LLM-driven firing.** Once a week per consumer, an LLM call will
decide whether anything happened given the persona's state, picking
from the Holmes-Rahe vocabulary in `world/life_events_vocab.yaml`.
The vocabulary ships now in v0 so v1 can plug this in without
changes to scenarios or anything downstream.

**Why ship vocabulary now if we're not using it?** Because adding
the LLM-driven path in v1 is cleaner if the vocabulary, schema, and
diff-apply mechanism are already in place. v0 exercises everything
except the firing decision.

### 5.4 Reflection cycle (`agents/reflection.py`)

Adopted from Park et al., "Generative Agents" (Stanford, 2023). Every
simulated week, per persona, the LLM summarizes the week into 2–3
abstract observations. These are:
- Stored in `runtime.reflections` (in-memory)
- Emitted as `reflection` events to the event log
- Re-injected into future `decide()` prompts

The point: without reflections, agents tend toward "average plausible
human" over long runs. With reflections, they form a stable
self-model — *"Maya has become more cautious since losing her
position"* — that shapes future decisions and makes the persona feel
like one coherent character over months.

### 5.5 Catalog & pricing (`world/catalog.py`)

- 55 SKUs across 3 categories (groceries 25, electronics 15, dining 15).
- 2 retailers: ValueMart (discount, `price_mult: 0.85`) and EveryStore
  (mainstream, `price_mult: 1.00`).
- Pricing formula:

  ```
  consumer_price = base_price
                 × retailer.price_mult
                 × (1 + macro.inflation_rate)
                 × (1 + scenario_knob_for_category)
  ```

  This is the lever that makes counterfactuals work. The
  `electronics_shock.yaml` scenario sets
  `category_knobs.electronics: 0.20` → all electronics see prices
  +20% relative to baseline.

The catalog is **fixed at startup** in v0. v1 plan: on-demand SKU
materialization — when a consumer requests something not in the
catalog ("vintage record player"), an LLM call generates the SKU and
caches it.

### 5.6 Scenarios & knobs (`scenarios/`)

A scenario is YAML:

```yaml
scenario_id: my_scenario
start_date: 2026-01-01
n_ticks: 90
seed: 42

macro:
  inflation_rate: 0.03
  unemployment_rate: 0.04
  consumer_sentiment: 0.55

category_knobs:
  electronics: 0.20    # +20% across the board on electronics

scripted_events:
  - day: 45
    agent_id: persona-maya-001
    event_id: fired_from_work
    dna_diff:
      economics.employment_status: unemployed
```

**v0 knob types**:
- `category_knobs`: multiplier offsets per category (the pricing
  formula consumes these).
- `macro.*` overrides: inflation, unemployment, sentiment — these flow
  into the LLM prompts and the pricing formula.
- `scripted_events`: narrative pins.
- `notes`: free-text that goes into the LLM prompt as scenario context.

A counterfactual = same baseline + one knob changed. Re-run with the
same seed; diff the event streams.

### 5.7 Datalake (`datalake/`)

**Events table** (one wide Parquet file per run):
```
agent_id   str
tick_day   date
seq        int             # ordering within a tick
event_type str             # one of: view, cart_add, purchase,
                           #   abandon, return, life_event,
                           #   income, expense, reflection
payload    json (str)      # event-specific
scenario_id str
run_id     uuid
```

**Snapshots table** (separate file, narrow typed columns):
```
agent_id, tick_day, kind, cash_usd, savings_usd, debt_total_usd,
employment_status, dna_blob (json, weekly rows only)
```

**DuckDB typed views** (`datalake/queries.py`): one view per event
type with `json_extract_string(payload, '$.field')` projections so
notebook queries don't have to parse JSON inline. Created on-demand
by `open_run(run_dir)`.

Why this design? Single writer = simple code path. Typed views =
ergonomic queries. Schema evolution is painless (new event type? add
a view). The Parquet layout is also compatible with S3 + Iceberg if
we ever graduate to cloud — that's a config flip, not a rewrite.

---

## 6. The architectural pattern (the project's signature)

> **Tiny structured seed + LLM at runtime + cache for reproducibility.**

Instead of hand-crafting "what does Maya remember" structures, we let
the LLM synthesize weekly reflections. Instead of authoring thousands
of SKUs, we seed ~55 (and in v1, materialize novel SKUs on demand).
Instead of authoring 43 life events with eligibility predicates and
rate distributions, we commit a 43-row vocabulary file (`{id, lcu,
group}`) and (in v1) let the LLM decide eligibility / firing / diffs
at runtime.

The trade: some determinism for *much* less authoring code and richer
emergent behavior. We pay with LLM cost — mitigated in v1 by prompt
caching, async fan-out, and the Anthropic Batches API for 50% cheaper
async completions.

This pattern is the most interesting article material. It's the
through-line between three otherwise-different subsystems.

---

## 7. How to extend

### Add a new persona
1. Write `personas/<name>.yaml` following the Maya/Raj/Elena schema.
2. That's it. `load_personas()` picks it up from the directory.

### Add a new SKU
1. Append to `world/catalog_seed_<category>.yaml`.
2. Done. The catalog loader merges all three category files.

### Add a new category
1. Create `world/catalog_seed_<category>.yaml`.
2. Add the category name to each retailer's `assortment` in
   `world/retailers.yaml`.
3. Update `consumer_agents/world/catalog.py:load_catalog()` to include
   the new file.

### Add a new event type
1. Add the string to `EVENT_TYPES` in `datalake/events.py`.
2. Add a typed view to `datalake/queries.py:VIEW_DEFS`.
3. Emit it from wherever it originates (`DecisionEngine`, scheduler).

### Add a new life event (v0)
1. Append to `world/life_events_vocab.yaml`.
2. Reference it from a scenario's `scripted_events` with a `dna_diff`.
   In v1 the LLM will pick it up automatically; in v0 only scripted
   firings use it.

### Add a new scenario
1. Copy `examples/baseline.yaml`, change `scenario_id`, tweak knobs.
2. `consumer-agents run examples/<scenario>.yaml`.

### Add a new scenario knob type
This is the only extension that touches multiple files:
1. Add the field to `scenarios/schema.py:ScenarioConfig`.
2. Plumb it from `RunConfig` (in `agents/scheduler.py`) into
   wherever it should bite — usually the pricing formula or the LLM
   prompt.

### Switch the LLM model
Pass `--model claude-opus-4-7` to `consumer-agents run`, or change the
default in `agents/decision.py:DEFAULT_MODEL`.

---

## 8. Honest caveats

These are the framing rules for any article or claim built on the
output. They are intentional and we should not pretend otherwise.

- **Not market research.** With 3 LLM-driven personas, output is
  plausible but not empirically validated. Frame articles around
  technique, not predictions.
- **Scenarios are tautological at small N.** A price-sensitive persona
  reduces electronics purchases when electronics prices rise — that's
  the prompt, not a finding. Magnitudes will not match real
  elasticities.
- **The "datalake" is small.** Hundreds of thousands of events from
  3–200 simulated agents. Useful for demonstrating datalake patterns;
  not a substitute for real behavior data.
- **The agent-simulation space is crowded in 2026.** Standing-out
  content must lean on specifics (caching architecture, the
  seed+LLM+cache pattern, what the LLM gets wrong, evaluation
  methodology) rather than the general premise.

---

## 9. v0 → v1 roadmap

What we deliberately deferred to keep v0 shippable:

| Subsystem | v0 (now) | v1 (planned) |
| --- | --- | --- |
| Personas | 3 hand-crafted | + procedural generator + preference learning (EMA) |
| Catalog | Fixed at startup | On-demand SKU materialization via LLM |
| Retailers | 2 (discount + mainstream) | + premium tier |
| Life events | Scripted-only, 10-event Holmes-Rahe vocab | LLM-driven weekly firing; full 43-event vocab |
| Decision routing | Single LLM call per consumer-day | Routine/non-routine routing to cut LLM cost at 1000+ agents |
| Scheduler | Synchronous | Async fan-out + Anthropic Batches API + prompt caching + sharding |
| Memory | Recent events + weekly reflections | Importance-weighted retrieval (full Park-et-al memory stream) |
| Datalake | Single events.parquet + snapshots.parquet | + dbt-duckdb models, partitioned writes |
| Time model | Daily tick | + intra-day event queue (browsing sessions, cart timers) |
| Scenarios | Category knobs + scripted events | + supply shocks, marketing campaigns, scenario sweeps |
| Notebooks | 1 comparison notebook | dbt models + dashboards |

The architecture was designed so each v1 item is **additive**, not a
rewrite. The `DecisionEngine` adapter lets us slot in async, batches,
and caching without touching the scheduler. The Parquet layout already
matches S3 + Iceberg conventions for cloud graduation.

---

## 10. Where to start reading the code

If you're new to this codebase, read in this order:

1. `consumer_agents/personas/dna.py` — what a consumer *is*.
2. `personas/maya.yaml` — a concrete example.
3. `consumer_agents/world/catalog.py` — what they shop against.
4. `consumer_agents/agents/decision.py` — how they choose.
5. `consumer_agents/agents/loop.py:step` — what happens to one consumer in one day.
6. `consumer_agents/agents/scheduler.py:run_scheduler` — the outer loop.
7. `consumer_agents/world/life_events.py` — how state mutates over time.
8. `consumer_agents/datalake/{events,snapshots,queries}.py` — what we record.
9. `examples/baseline.yaml` and `examples/electronics_shock.yaml` — the user surface.

That's about 1,500 lines total. The pieces interlock cleanly; once
you've read `decision.py` and `scheduler.py` the rest falls into
place.
