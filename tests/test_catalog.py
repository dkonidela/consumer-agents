"""Unit tests for catalog loading + pricing formula."""

from __future__ import annotations

from pathlib import Path

from consumer_agents.world.catalog import consumer_price, load_catalog
from consumer_agents.world.macro import MacroState


def test_load_catalog():
    repo = Path(__file__).resolve().parent.parent
    cat = load_catalog(repo / "world")
    assert len(cat.skus) > 30
    assert len(cat.retailers) == 2
    assert "groceries" in cat.categories
    assert "electronics" in cat.categories
    assert "dining" in cat.categories


def test_pricing_formula():
    repo = Path(__file__).resolve().parent.parent
    cat = load_catalog(repo / "world")
    sku = cat.skus[0]
    valuemart = cat.retailer_by_id("ret-valuemart")
    everystore = cat.retailer_by_id("ret-everystore")
    macro = MacroState(inflation_rate=0.0)

    p_value = consumer_price(sku, valuemart, macro, 0.0)
    p_main = consumer_price(sku, everystore, macro, 0.0)
    # Discount retailer should be cheaper.
    assert p_value < p_main

    # +20% scenario knob bumps the price.
    p_main_shock = consumer_price(sku, everystore, macro, 0.20)
    assert p_main_shock == p_main * 1.20
