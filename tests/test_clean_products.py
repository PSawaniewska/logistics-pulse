"""
Tests for the category translation logic in cleaning/clean_products.py.
"""

import pandas as pd

from cleaning.clean_products import clean_products, translate_categories


def products(categories: list[str | None]) -> pd.DataFrame:
    """Build a products frame from a list of Portuguese category names."""
    return pd.DataFrame({
        "product_id": [f"P{i}" for i in range(len(categories))],
        "product_category_name": categories,
        "product_weight_g": [100] * len(categories),
    })


def translation() -> pd.DataFrame:
    """Build a translation table holding a single known category."""
    return pd.DataFrame({
        "product_category_name": ["cama_mesa_banho"],
        "product_category_name_english": ["bed_bath_table"],
    })


def test_translate_categories_uses_the_official_translation_table():
    # Arrange
    df = products(["cama_mesa_banho"])

    # Act
    result = translate_categories(df, translation())

    # Assert
    assert result.iloc[0] == "bed_bath_table"


def test_translate_categories_fills_a_category_the_table_is_missing():
    # pc_gamer has no row in Olist's translation table
    df = products(["pc_gamer"])

    result = translate_categories(df, translation())

    assert result.iloc[0] == "gaming_pc"


def test_translate_categories_leaves_a_product_without_a_category_empty():
    df = products([None])

    result = translate_categories(df, translation())

    assert pd.isna(result.iloc[0])


def test_clean_products_returns_only_the_product_id_and_the_category():
    df = products(["cama_mesa_banho"])

    result = clean_products(df, translation())

    assert list(result.columns) == ["product_id", "product_category"]