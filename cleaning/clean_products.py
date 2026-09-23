"""
Cleans the raw Olist products table and translates category names to English.
"""

import pandas as pd

RAW_PRODUCTS_PATH = "../data/raw/olist_products_dataset.csv"
RAW_TRANSLATION_PATH = "../data/raw/product_category_name_translation.csv"
PROCESSED_PATH = "../data/processed/products.parquet"

# Two categories are missing from Olist's own translation table. The dataset is
# a closed 2016-2018 archive, so these names cannot go stale.
MISSING_TRANSLATIONS = {
    "pc_gamer": "gaming_pc",
    "portateis_cozinha_e_preparadores_de_alimentos": "small_appliances_kitchen_and_food_preparation",
}


def load_products(path: str = RAW_PRODUCTS_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def load_translation(path: str = RAW_TRANSLATION_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


# A lookup keyed by category is safer here than a merge: it cannot multiply rows,
# and an untranslated category stays visibly empty instead of silently vanishing.
def translate_categories(products: pd.DataFrame, translation: pd.DataFrame) -> pd.Series:
    """Map each product's Portuguese category to its English name."""
    lookup = dict(
        zip(
            translation["product_category_name"],
            translation["product_category_name_english"],
        )
    )
    lookup.update(MISSING_TRANSLATIONS)

    return products["product_category_name"].map(lookup)


def clean_products(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    """Reduce the raw products table to one English category per product."""
    df = products.copy()
    df["product_category"] = translate_categories(products, translation)

    # Weight, dimensions and listing-quality columns answer none of the
    # project's questions - see the notes for the measurement behind that.
    return df[["product_id", "product_category"]]


def main():
    products = load_products()
    translation = load_translation()
    df = clean_products(products, translation)
    df.to_parquet(PROCESSED_PATH, index=False)

    print("rows:", len(df))
    print("categories:", df["product_category"].nunique())
    print("products without category:", df["product_category"].isna().sum())


if __name__ == "__main__":
    main()