from typing import Any

from app.product_loader import load_products


ATTRIBUTE_KEYWORDS = {
    "weight": ["重量"],
    "color": ["顏色"],
    "shape": ["形狀"],
    "size": ["大小", "尺寸"],
}


def parse_command(text: str) -> dict[str, Any]:
    product_name = None
    for product in load_products():
        candidate = product.get("product_name")
        if candidate and candidate in text:
            product_name = candidate
            break

    requested_attributes: list[str] = []
    for attribute, keywords in ATTRIBUTE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            requested_attributes.append(attribute)

    return {
        "product_name": product_name,
        "requested_attributes": requested_attributes,
    }
