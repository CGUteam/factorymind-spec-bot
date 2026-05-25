from typing import Any

from app.product_loader import find_product_by_name, load_products
from app.rag_retriever import search_by_rag


def _find_by_color_shape_rule(text: str) -> dict[str, Any] | None:
    products = load_products()
    colors = sorted({p.get("color") for p in products if p.get("color")}, key=len, reverse=True)
    shapes = sorted({p.get("shape") for p in products if p.get("shape")}, key=len, reverse=True)

    matched_color = next((c for c in colors if c in text), None)
    matched_shape = next((s for s in shapes if s in text), None)
    if not matched_color or not matched_shape:
        return None

    for product in products:
        if product.get("color") == matched_color and product.get("shape") == matched_shape:
            return product
    return None


def retrieve_product(text: str, parsed_command: dict[str, Any]) -> dict[str, Any] | None:
    product_name = parsed_command.get("product_name")
    if product_name is not None:
        product = find_product_by_name(product_name)
        if product is not None:
            return {"product": product, "matched_by": "exact_name"}

    product = _find_by_color_shape_rule(text)
    if product is not None:
        return {"product": product, "matched_by": "color_shape_rule"}

    return search_by_rag(text)
