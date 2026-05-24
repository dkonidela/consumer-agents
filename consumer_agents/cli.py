"""consumer-agents CLI (typer-based)."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from consumer_agents.datalake.queries import open_run
from consumer_agents.scenarios.runner import run_scenario


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Tiny dotenv loader. Reads KEY=VALUE lines from `.env` in CWD and
    populates os.environ for any keys not already set. Lines starting
    with `#` and blank lines are ignored. Quotes around values are stripped.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

app = typer.Typer(help="consumer-agents — agent simulation engine")
console = Console()


@app.command()
def run(
    scenario: Path = typer.Argument(..., exists=True, readable=True, help="Path to scenario YAML"),
    model: str | None = typer.Option(None, help="Override the LLM model"),
    run_root: Path = typer.Option(Path("runs"), help="Directory to write runs into"),
) -> None:
    """Execute a scenario end-to-end."""
    console.print(f"[bold]Running scenario:[/bold] {scenario}")
    out = run_scenario(scenario_path=scenario, run_root=run_root, model=model)
    console.print(f"[green]Run complete[/green] → {out}")


@app.command()
def analyze(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Print a quick summary of a run's events."""
    con = open_run(run_dir)
    console.print(f"[bold]Run:[/bold] {run_dir}")

    counts = con.execute(
        "SELECT event_type, COUNT(*) AS n FROM events GROUP BY 1 ORDER BY n DESC"
    ).fetchall()
    t1 = Table(title="Event counts")
    t1.add_column("event_type")
    t1.add_column("n", justify="right")
    for et, n in counts:
        t1.add_row(et, str(n))
    console.print(t1)

    try:
        per_agent = con.execute(
            """
            SELECT agent_id, COUNT(*) AS purchases, ROUND(SUM(total_usd), 2) AS spend_usd
            FROM v_purchases GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        t2 = Table(title="Purchases by agent")
        t2.add_column("agent_id")
        t2.add_column("purchases", justify="right")
        t2.add_column("spend_usd", justify="right")
        for a, p, s in per_agent:
            t2.add_row(a, str(p), str(s))
        console.print(t2)
    except Exception:
        pass


@app.command()
def init(
    target: Path = typer.Option(
        Path("examples/new_scenario.yaml"),
        help="Where to write the scaffold scenario YAML",
    ),
) -> None:
    """Write a starter scenario YAML."""
    if target.exists():
        console.print(f"[red]{target} already exists[/red]")
        raise typer.Exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """scenario_id: my-scenario
start_date: 2026-01-01
n_ticks: 30
seed: 0
notes:
  - my notes

macro:
  inflation_rate: 0.03
  unemployment_rate: 0.04
  consumer_sentiment: 0.5

category_knobs:
  electronics: 0.0

scripted_events: []
"""
    )
    console.print(f"[green]Scaffold written to {target}[/green]")


if __name__ == "__main__":
    app()
