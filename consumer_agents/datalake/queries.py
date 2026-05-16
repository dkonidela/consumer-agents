"""DuckDB query helpers + typed views over the wide events table."""

from __future__ import annotations

from pathlib import Path

import duckdb

VIEW_DEFS: dict[str, str] = {
    "v_views": """
        SELECT agent_id, tick_day, seq,
               json_extract_string(payload, '$.category') AS category,
               json_extract_string(payload, '$.sku_id')   AS sku_id,
               json_extract_string(payload, '$.retailer') AS retailer,
               TRY_CAST(json_extract_string(payload, '$.price_shown') AS DOUBLE) AS price_shown
        FROM events WHERE event_type = 'view'
    """,
    "v_purchases": """
        SELECT agent_id, tick_day, seq,
               json_extract_string(payload, '$.cart_id')  AS cart_id,
               TRY_CAST(json_extract_string(payload, '$.total_usd') AS DOUBLE) AS total_usd,
               json_extract_string(payload, '$.retailer') AS retailer
        FROM events WHERE event_type = 'purchase'
    """,
    "v_cart_add": """
        SELECT agent_id, tick_day, seq,
               json_extract_string(payload, '$.sku_id')   AS sku_id,
               TRY_CAST(json_extract_string(payload, '$.qty') AS INTEGER) AS qty,
               json_extract_string(payload, '$.retailer') AS retailer,
               TRY_CAST(json_extract_string(payload, '$.unit_price_usd') AS DOUBLE) AS unit_price_usd
        FROM events WHERE event_type = 'cart_add'
    """,
    "v_abandon": """
        SELECT agent_id, tick_day, seq,
               json_extract_string(payload, '$.cart_id') AS cart_id,
               json_extract_string(payload, '$.reason')  AS reason
        FROM events WHERE event_type = 'abandon'
    """,
    "v_return": """
        SELECT agent_id, tick_day, seq,
               json_extract_string(payload, '$.order_id') AS order_id,
               json_extract_string(payload, '$.sku_id')   AS sku_id,
               json_extract_string(payload, '$.reason')   AS reason
        FROM events WHERE event_type = 'return'
    """,
    "v_life_events": """
        SELECT agent_id, tick_day, seq,
               json_extract_string(payload, '$.event_id')  AS event_id,
               TRY_CAST(json_extract_string(payload, '$.lcu') AS INTEGER) AS lcu,
               json_extract_string(payload, '$.narration') AS narration
        FROM events WHERE event_type = 'life_event'
    """,
    "v_income": """
        SELECT agent_id, tick_day, seq,
               TRY_CAST(json_extract_string(payload, '$.amount_usd') AS DOUBLE) AS amount_usd,
               json_extract_string(payload, '$.source') AS source
        FROM events WHERE event_type = 'income'
    """,
    "v_expense": """
        SELECT agent_id, tick_day, seq,
               TRY_CAST(json_extract_string(payload, '$.amount_usd') AS DOUBLE) AS amount_usd,
               json_extract_string(payload, '$.category') AS category
        FROM events WHERE event_type = 'expense'
    """,
    "v_reflections": """
        SELECT agent_id, tick_day, seq, payload
        FROM events WHERE event_type = 'reflection'
    """,
}


def open_run(run_dir: str | Path) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection wired to a run's Parquet outputs.

    Creates views: events (raw), snapshots (raw), and one typed view
    per event_type.
    """
    run_dir = Path(run_dir)
    con = duckdb.connect(":memory:")
    events_path = run_dir / "events.parquet"
    snapshots_path = run_dir / "snapshots.parquet"

    if events_path.exists():
        con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{events_path}')")
        for view_name, sql in VIEW_DEFS.items():
            con.execute(f"CREATE VIEW {view_name} AS {sql}")
    if snapshots_path.exists():
        con.execute(
            f"CREATE VIEW snapshots AS SELECT * FROM read_parquet('{snapshots_path}')"
        )
    return con
