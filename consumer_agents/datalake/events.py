"""Event store — append-only Parquet writer for the 9 v0 event types."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

EVENT_TYPES = {
    "view",
    "cart_add",
    "purchase",
    "abandon",
    "return",
    "life_event",
    "income",
    "expense",
    "reflection",
}


@dataclass
class Event:
    agent_id: str
    tick_day: date
    seq: int
    event_type: str
    payload: dict[str, Any]
    scenario_id: str
    run_id: str

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event_type: {self.event_type!r}")


_SCHEMA = pa.schema(
    [
        ("agent_id", pa.string()),
        ("tick_day", pa.date32()),
        ("seq", pa.int32()),
        ("event_type", pa.string()),
        ("payload", pa.string()),  # JSON string
        ("scenario_id", pa.string()),
        ("run_id", pa.string()),
    ]
)


@dataclass
class EventWriter:
    """Buffers events in memory and flushes to a Parquet file on close.

    For v0 (3 agents × 90 days × handful of events/day) this is trivially
    small — a single Parquet file per run is fine. Scaling to row-group
    rotation or partitioned writes is a v1 concern.
    """

    out_path: Path
    scenario_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _buffer: list[Event] = field(default_factory=list)
    _seq_counters: dict[tuple[str, date], int] = field(default_factory=dict)

    def append(
        self,
        agent_id: str,
        tick_day: date,
        event_type: str,
        payload: dict[str, Any],
    ) -> Event:
        key = (agent_id, tick_day)
        seq = self._seq_counters.get(key, 0)
        self._seq_counters[key] = seq + 1
        evt = Event(
            agent_id=agent_id,
            tick_day=tick_day,
            seq=seq,
            event_type=event_type,
            payload=payload,
            scenario_id=self.scenario_id,
            run_id=self.run_id,
        )
        self._buffer.append(evt)
        return evt

    def flush(self) -> None:
        """Write buffered events to Parquet (overwrites)."""
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        rows = {
            "agent_id": [e.agent_id for e in self._buffer],
            "tick_day": [e.tick_day for e in self._buffer],
            "seq": [e.seq for e in self._buffer],
            "event_type": [e.event_type for e in self._buffer],
            "payload": [json.dumps(e.payload, default=str) for e in self._buffer],
            "scenario_id": [e.scenario_id for e in self._buffer],
            "run_id": [e.run_id for e in self._buffer],
        }
        table = pa.Table.from_pydict(rows, schema=_SCHEMA)
        pq.write_table(table, self.out_path)

    def __len__(self) -> int:
        return len(self._buffer)
