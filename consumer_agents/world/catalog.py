"""Catalog — SKUs, retailers, and the pricing formula."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from consumer_agents.world.macro import MacroState


class SKU(BaseModel):
    id: str
    name: str
    category: str
    subcategory: str | None = None
    brand: str = "store-brand"
    quality_tier: str = "standard"  # budget | standard | mid | premium
    eco_score: float = Field(ge=0, le=1, default=0.5)
    base_price_usd: float = Field(ge=0)
    source: str = "seed"  # seed | generated


class Retailer(BaseModel):
    id: str
    name: str
    positioning: str  # discount | mainstream | premium
    price_mult: float = Field(gt=0)
    assortment: list[str]  # categories this retailer carries
    channel: str = "mixed"  # online_first | in_store | mixed

    def carries(self, category: str) -> bool:
        return category in self.assortment


class Catalog(BaseModel):
    skus: list[SKU]
    retailers: list[Retailer]

    def skus_by_category(self, category: str) -> list[SKU]:
        return [s for s in self.skus if s.category == category]

    def retailer_by_id(self, retailer_id: str) -> Retailer | None:
        return next((r for r in self.retailers if r.id == retailer_id), None)

    def retailers_for_category(self, category: str) -> list[Retailer]:
        return [r for r in self.retailers if r.carries(category)]

    def sku_by_id(self, sku_id: str) -> SKU | None:
        return next((s for s in self.skus if s.id == sku_id), None)

    @property
    def categories(self) -> list[str]:
        return sorted({s.category for s in self.skus})


def consumer_price(
    sku: SKU,
    retailer: Retailer,
    macro: MacroState,
    scenario_knob: float = 0.0,
) -> float:
    """Pricing formula:

        consumer_price = base_price * retailer.price_mult
                       * (1 + macro.inflation_rate)
                       * (1 + scenario_knob)

    The scenario_knob is the category/SKU-targeted multiplier from a
    counterfactual scenario (e.g., 0.20 for "electronics +20%").
    """
    return (
        sku.base_price_usd
        * retailer.price_mult
        * (1 + macro.inflation_rate)
        * (1 + scenario_knob)
    )


def load_catalog(world_dir: str | Path) -> Catalog:
    """Load the v0 catalog from seed YAMLs in `world/`.

    Reads:
      - catalog_seed_groceries.yaml
      - catalog_seed_electronics.yaml
      - catalog_seed_dining.yaml
      - retailers.yaml
    """
    world = Path(world_dir)
    sku_files = [
        world / "catalog_seed_groceries.yaml",
        world / "catalog_seed_electronics.yaml",
        world / "catalog_seed_dining.yaml",
    ]
    skus: list[SKU] = []
    for f in sku_files:
        if not f.exists():
            continue
        with open(f) as fh:
            rows = yaml.safe_load(fh) or []
            skus.extend(SKU(**r) for r in rows)

    retailers_path = world / "retailers.yaml"
    with open(retailers_path) as fh:
        retailer_rows = yaml.safe_load(fh) or []
        retailers = [Retailer(**r) for r in retailer_rows]

    return Catalog(skus=skus, retailers=retailers)
