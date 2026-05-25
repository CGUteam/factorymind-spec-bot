import math
from typing import Any

import requests

from app.product_loader import load_products


OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "bge-m3"
SIMILARITY_THRESHOLD = 0.5

_product_embeddings: list[dict[str, Any]] | None = None


def _format_size(size: dict[str, Any]) -> str:
    unit = size.get("unit", "")
    if all(key in size for key in ("length", "width", "height")):
        return f"{size['length']}x{size['width']}x{size['height']} {unit}".strip()
    if "diameter" in size and "height" in size:
        return f"直徑{size['diameter']}x高{size['height']} {unit}".strip()
    if "diameter" in size:
        return f"直徑{size['diameter']} {unit}".strip()
    return "、".join(f"{key}:{value}" for key, value in size.items())


def product_to_searchable_text(product: dict[str, Any]) -> str:
    size_text = _format_size(product.get("size", {}))
    return (
        f"產品名稱：{product.get('product_name')}。"
        f"顏色：{product.get('color')}。"
        f"形狀：{product.get('shape')}。"
        f"重量：{product.get('weight')}g。"
        f"大小：{size_text}。"
    )


def _get_embedding(text: str) -> list[float] | None:
    try:
        response = requests.post(
            OLLAMA_EMBEDDING_URL,
            json={"model": EMBEDDING_MODEL, "prompt": text},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            print(f"[rag_retriever] Ollama 回應沒有有效 embedding：{data}")
            return None
        return [float(v) for v in embedding]
    except requests.exceptions.ConnectionError:
        print("[rag_retriever] 無法連線到 Ollama，請確認 Ollama 已啟動於 http://localhost:11434")
    except requests.exceptions.Timeout:
        print("[rag_retriever] 呼叫 Ollama embedding API 逾時")
    except requests.exceptions.HTTPError as exc:
        print(f"[rag_retriever] Ollama embedding API HTTP 錯誤：{exc}")
    except requests.exceptions.RequestException as exc:
        print(f"[rag_retriever] Ollama embedding API 請求失敗：{exc}")
    except (ValueError, TypeError) as exc:
        print(f"[rag_retriever] 解析 Ollama embedding 回應失敗：{exc}")
    return None


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if len(vector_a) != len(vector_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _ensure_product_embeddings() -> list[dict[str, Any]] | None:
    global _product_embeddings
    if _product_embeddings is not None:
        return _product_embeddings

    embeddings: list[dict[str, Any]] = []
    for product in load_products():
        text = product_to_searchable_text(product)
        embedding = _get_embedding(text)
        if embedding is None:
            print(f"[rag_retriever] 無法建立產品 embedding：{product.get('product_name')}")
            return None
        embeddings.append({"product": product, "searchable_text": text, "embedding": embedding})

    _product_embeddings = embeddings
    return _product_embeddings


def search_by_rag(text: str) -> dict[str, Any] | None:
    product_embeddings = _ensure_product_embeddings()
    if not product_embeddings:
        return None

    query_embedding = _get_embedding(text)
    if query_embedding is None:
        return None

    best_match: dict[str, Any] | None = None
    best_similarity = -1.0
    for item in product_embeddings:
        similarity = _cosine_similarity(query_embedding, item["embedding"])
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = item

    if best_match is None or best_similarity < SIMILARITY_THRESHOLD:
        return None

    return {
        "product": best_match["product"],
        "matched_by": "rag_bge_m3",
        "similarity": round(best_similarity, 4),
    }
