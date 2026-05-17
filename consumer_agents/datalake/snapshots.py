"""Snapshot store — daily economics + weekly DNA dumps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from consumer_agents.personas.dna import Persona

_SCHEMA = pa.schema(
    [
        ("agent_id", pa.string()),
        ("tick_day", pa.date32()),
        ("kind", pa.string()),  # 'daily_econ' | 'weekly_dna'
        ("cash_usd", pa.float64()),
        ("savings_usd", pa.float64()),
        ("debt_total_usd", pa.float64()),
        ("employment_status", pa.string()),
        ("dna_blob", pa.string()),  # JSON string, null for daily rows
    ]
)


@dataclass
class SnapshotWriter:
    out_path: Path
    _rows: list[dict] = field(default_factory=list)

    def append_daily(self, agent_id: str, tick_day: date, persona: Persona, cash_usd: float) -> None:
        self._rows.append(
            {
                "agent_id": agent_id,
                "tick_day": tick_day,
                "kind": "daily_econ",
                "cash_usd": cash_usd,
                "savings_usd": persona.economics.savings_usd,
                "debt_total_usd": persona.economics.debt.total,
                "employment_status": persona.economics.employment_status.value,
                "dna_blob": None,
            }
        )

    def append_weekly_dna(self, agent_id: str, tick_day: date, persona: Persona, cash_usd: float) -> None:
        self._rows.append(
            {
                "agent_id": agent_id,
                "tick_day": tick_day,
                "kind": "weekly_dna",
                "cash_usd": cash_usd,
                "savings_usd": persona.economics.savings_usd,
                "debt_total_usd": persona.economics.debt.total,
                "employment_status": persona.economics.employment_status.value,
                "dna_blob": persona.model_dump_json(),
            }
        )

    def flush(self) -> None:
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        cols = {k: [r[k] for r in self._rows] for k in _SCHEMA.names}
        table = pa.Table.from_pydict(cols, schema=_SCHEMA)
        pq.write_table(table, self.out_path)
