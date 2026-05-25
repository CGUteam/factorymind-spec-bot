import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"


@lru_cache(maxsize=1)
def load_products() -> list[dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def find_product_by_name(product_name: str) -> dict[str, Any] | None:
    for product in load_products():
        if product.get("product_name") == product_name:
            return product
    return None
