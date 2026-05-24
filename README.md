# consumer-agents

> Open source agent simulation engine: synthetic consumers with structured DNA living in a retail world. Produces a queryable behavior datalake for counterfactual analysis.

**Status: v0, early.** Placeholder name. Spec lives at `docs/SPEC.md`.

## What it is

A small society of "digital humans" (3 in v0, scaling later) live day-to-day lives: working, browsing, buying, reacting to life events. Each consumer has structured DNA (Big Five personality, economics, life stage, preferences). A stateless `BehaviorEngine` makes one LLM call (Anthropic) per consumer per day to decide what they do. Life events (scripted in v0 from the Holmes-Rahe vocabulary; LLM-driven in v1) mutate state over time. Output lands in Parquet + DuckDB, ready for analysis and articles.

## Why

A learning vehicle. Each subsystem (DNA, catalog, life events, datalake, scheduler, scenarios) is a distinct technical topic for deep technical articles. The architectural signature — *tiny structured seed + LLM at runtime + cache for reproducibility* — is the through-line.

## What it isn't

Not market research. Not predictive of real consumer behavior. With 3 LLM-driven personas, output is plausible but not empirically validated. Frame articles around technique, not predictions.

## v0 scope

- 3 hand-crafted personas (Maya, Raj, Elena)
- 3 categories (groceries, electronics, dining), 2 retailers (discount + mainstream)
- 10 life events from Holmes-Rahe (scripted firing in v0; LLM-driven firing in v1)
- Sync daily-tick scheduler
- 1 baseline scenario + 1 counterfactual (electronics +20%)
- Local Parquet + DuckDB datalake

## What each LLM call sees

For every simulated day, the `BehaviorEngine` makes one Anthropic API call per consumer. The prompt is composed of:

**System prompt** — consistent per call, identifies the persona:

```
You are simulating one synthetic consumer's behavior for a single day...

CONSUMER: Maya Patel, 28, PhD student (CS) in Boston. Earns $2,400/mo,
$3,200 savings, $48,000 in debt. Highly open to new things, conscientious
and planned, very price-sensitive, eco-conscious. Student stage,
household of 2 (roommates).

WORLD MACRO STATE: Inflation: 3.0% | Unemployment: 4.0% | Consumer
sentiment: 0.55
```

**User prompt** — changes every tick:

```
Today is day 30 (2026-01-31, Sat).
Cash on hand: $1,847.50
Scenario price adjustments: (none)

CATALOG: <55 SKUs across groceries/electronics/dining, with brand,
quality tier, price>
RETAILERS: <ValueMart 0.85×, EveryStore 1.00×>

RECENT EVENTS (last 15):
  - day 28: expense {amount_usd: 1605.0, category: recurring}
  - day 28: income {amount_usd: 1200.0, source: payday}
  - day 27: purchase {total_usd: 24.50, retailer: ret-valuemart}
  - day 27: cart_add {sku_id: sku-groc-001, ...}
  - day 27: view {category: groceries, ...}
  ...

RECENT REFLECTIONS:
  - Maya has been steadily building grocery routines around ValueMart...
  - She's resisted any electronics purchase despite browsing earlier...

Decide what (if anything) this consumer does today.
```

**Per-call context summary:**

| Context | Source | Coverage |
| --- | --- | --- |
| Who they are | `Persona.to_prompt()` | Full DNA summary (~3 sentences) |
| What they have | `cash_usd` | Live, accurate |
| What they did recently | Last 15 events from in-memory buffer | Roughly the last 1–3 days of activity |
| Their self-model | Last 3 weekly reflections | LLM-generated compressed long-term memory |
| The world | Full catalog + retailers + macro | Refreshed every call |

**Known v0 limitations of this context model:**

- **Memory horizon is short.** The 15-event buffer fills with shopping events quickly; by day 30 the LLM likely can't see day-1 purchases directly, only what the weekly reflections preserved. Importance-weighted retrieval (Park et al., 2023) is planned for v1.
- **No aggregate stats.** The LLM sees the raw event tail, not "Maya has spent $X on groceries this month." Long-term consistency depends on reflections doing that work.
- **DNA is sent as natural-language summary**, not raw JSON. Cheaper and cache-friendlier, but slightly less granular than `personas/maya.yaml`.
- **No catalog filtering.** Every call sees all 55 SKUs even if the persona is only shopping for groceries. Acceptable at v0 scale; the "two-stage intent loop" idea in `consumer-agents-journal/topics/blog-ideas.md` addresses this for v1+.

Full prompt-building code: `consumer_agents/agents/behavior.py` (`_build_system_prompt`, `_build_user_prompt`).

## Install

```bash
pip install -e ".[dev]"
```

## Run

Provide your Anthropic API key one of two ways:

- **Environment variable** (one-off): `export ANTHROPIC_API_KEY=sk-ant-...`
- **`.env` file** in the project root with `ANTHROPIC_API_KEY=sk-ant-...` (gitignored; auto-loaded by the CLI)

Then:

```bash
consumer-agents run examples/baseline.yaml
consumer-agents run examples/electronics_shock.yaml
consumer-agents analyze runs/<run_id>
```

Outputs land in `runs/<run_id>/events.parquet` and `runs/<run_id>/snapshots.parquet`. A 90-day run with 3 personas takes ~10–25 minutes and costs ~$10–20 in API usage (no prompt caching yet — that's v1).

## License

Apache-2.0.
