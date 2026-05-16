"""Open Food Facts loader (optional, off by default in v0).

The v0 catalog ships from hand-written YAMLs in `world/catalog_seed_*.yaml`.
This module is a stub for the v1 path where we pull a slice of Open Food
Facts and convert it to our SKU schema.

When implemented, this will:
  1. Download a CSV/Parquet slice from Open Food Facts (no API key needed;
     they publish full data dumps under the Open Database License).
  2. Filter to common US grocery categories with usable prices.
  3. Normalize into our `SKU` schema and write to `world/catalog_seed_groceries.parquet`.

For v0 we keep groceries in YAML alongside electronics and dining — see
`catalog_seed_groceries.yaml`. Replacing it with an Open Food Facts pull
is a contained v1 task.
"""

from __future__ import annotations

from pathlib import Path

OPEN_FOOD_FACTS_DUMP_URL = "https://static.openfoodfacts.org/data/openfoodfacts-products.csv.gz"


def load_from_open_food_facts(_out_path: str | Path) -> None:
    """Placeholder. Not implemented in v0."""
    raise NotImplementedError(
        "Open Food Facts loader is a v1 task. v0 uses the hand-written "
        "catalog_seed_groceries.yaml in `world/`."
    )
