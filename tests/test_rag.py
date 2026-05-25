"""
測試 RAG Spec 查詢模組：
- command_parser：規則解析
- product_retriever：三層查詢（精準名稱 / 顏色形狀 / RAG fallback）
- POST /query_spec：端點整合測試（含模糊比對）
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── 共用 fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """啟動 TestClient，mock 掉 ASR 模型與 LINE Bot init 避免真實連線。"""
    with patch("asr.load_model"), patch("line_bot.init"):
        import main
        with TestClient(main.app) as c:
            yield c


# ─── command_parser ───────────────────────────────────────────────────────────

class TestCommandParser:
    def test_exact_product_name(self):
        from app.command_parser import parse_command
        result = parse_command("請幫我檢查藍色方塊的重量和大小")
        assert result["product_name"] == "藍色方塊"
        assert "weight" in result["requested_attributes"]
        assert "size" in result["requested_attributes"]

    def test_no_product_name(self):
        from app.command_parser import parse_command
        result = parse_command("請查詢顏色與形狀")
        assert result["product_name"] is None
        assert "color" in result["requested_attributes"]
        assert "shape" in result["requested_attributes"]

    def test_no_attributes(self):
        from app.command_parser import parse_command
        result = parse_command("紅色圓球")
        assert result["product_name"] == "紅色圓球"
        assert result["requested_attributes"] == []


# ─── product_retriever ────────────────────────────────────────────────────────

class TestProductRetriever:
    def test_exact_name_match(self):
        from app.command_parser import parse_command
        from app.product_retriever import retrieve_product
        text = "請檢查黑色長方體的尺寸"
        parsed = parse_command(text)
        result = retrieve_product(text, parsed)
        assert result is not None
        assert result["matched_by"] == "exact_name"
        assert result["product"]["product_name"] == "黑色長方體"

    def test_color_shape_rule_match(self):
        from app.command_parser import parse_command
        from app.product_retriever import retrieve_product
        # 不含完整 product_name，但含顏色與形狀
        text = "我想知道綠色的圓柱重量"
        parsed = parse_command(text)
        # 手動清除 product_name 模擬解析不到完整名稱的情況
        parsed["product_name"] = None
        result = retrieve_product(text, parsed)
        assert result is not None
        assert result["matched_by"] == "color_shape_rule"
        assert result["product"]["product_name"] == "綠色圓柱"

    def test_not_found_without_rag(self):
        """RAG fallback 無法連線時應回傳 None，不崩潰。"""
        from app.command_parser import parse_command
        from app.product_retriever import retrieve_product
        text = "請找一個完全不存在的紫色星星"
        parsed = parse_command(text)
        parsed["product_name"] = None
        # mock _get_embedding 回傳 None 模擬 Ollama 離線
        with patch("app.rag_retriever._get_embedding", return_value=None):
            with patch("app.rag_retriever._product_embeddings", None):
                result = retrieve_product(text, parsed)
        assert result is None


# ─── /query_spec 端點 ─────────────────────────────────────────────────────────

class TestQuerySpecEndpoint:
    def test_known_product_known_items(self, client):
        """已知產品 + 已知檢查項目，應回傳對應 spec。"""
        resp = client.post("/query_spec", json={
            "product_name": "藍色方塊",
            "inspection_items": ["外觀缺陷", "重量"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_name"] == "藍色方塊"
        items = {i["name"]: i for i in data["inspection_items"]}
        assert items["外觀缺陷"]["threshold"] == 0.85
        assert items["外觀缺陷"]["method"] == "vision_detection"
        assert items["重量"]["standard"] == "100g ±5g"

    def test_known_product_unknown_item_uses_default(self, client):
        """已知產品但請求不存在的檢查項目，應回傳預設 spec。"""
        resp = client.post("/query_spec", json={
            "product_name": "紅色圓球",
            "inspection_items": ["不存在的項目"],
        })
        assert resp.status_code == 200
        data = resp.json()
        item = data["inspection_items"][0]
        assert item["name"] == "不存在的項目"
        assert item["threshold"] == 0.80
        assert item["standard"] == "無明顯缺陷"

    def test_unknown_product_returns_not_found(self, client):
        """找不到的產品，應回傳 product_found=False，不崩潰。"""
        with patch("app.rag_retriever._get_embedding", return_value=None):
            resp = client.post("/query_spec", json={
                "product_name": "不存在的產品",
                "inspection_items": ["外觀缺陷", "尺寸"],
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_found"] is False

    def test_known_product_returns_product_found_true(self, client):
        """已知產品應回傳 product_found=True。"""
        resp = client.post("/query_spec", json={
            "product_name": "藍色方塊",
            "inspection_items": ["外觀缺陷"],
        })
        assert resp.status_code == 200
        assert resp.json()["product_found"] is True

    def test_color_shape_fallback_via_endpoint(self, client):
        """LLM 輸出顏色+形狀描述（非完整名稱）時，應能靠規則比對到產品。"""
        resp = client.post("/query_spec", json={
            "product_name": "黃色三角形",
            "inspection_items": ["尺寸"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_name"] == "黃色三角形"
        assert data["inspection_items"][0]["method"] == "vision_detection"

    def test_all_five_products_reachable(self, client):
        """五筆產品都可精準查詢到。"""
        products = ["藍色方塊", "紅色圓球", "黃色三角形", "綠色圓柱", "黑色長方體"]
        for name in products:
            resp = client.post("/query_spec", json={
                "product_name": name,
                "inspection_items": ["外觀缺陷"],
            })
            assert resp.status_code == 200, f"{name} 查詢失敗"
            assert resp.json()["product_name"] == name


# ─── 模糊比對（LLM 後綴） ──────────────────────────────────────────────────────

class TestFuzzyMatching:
    """LLM 可能在項目名稱後加「檢查」、「檢測」等後綴，應仍能比對到正確 spec。"""

    @pytest.mark.parametrize("item_input,expected_threshold,expected_standard", [
        ("重量檢查",     0.90, "100g ±5g"),
        ("外觀缺陷檢查", 0.85, "無明顯刮痕、壓痕、異色"),
        ("尺寸檢測",     0.95, "邊長誤差 ±0.5mm 以內"),
        ("顏色檢查",     0.90, "色差 ΔE < 2.0"),
    ])
    def test_llm_suffix_still_matches(self, client, item_input, expected_threshold, expected_standard):
        resp = client.post("/query_spec", json={
            "product_name": "藍色方塊",
            "inspection_items": [item_input],
        })
        assert resp.status_code == 200
        item = resp.json()["inspection_items"][0]
        assert item["threshold"] == expected_threshold, f"{item_input} threshold 錯誤"
        assert item["standard"] == expected_standard, f"{item_input} standard 錯誤"

    def test_mixed_items_with_and_without_suffix(self, client):
        """同一次查詢中，有後綴與沒後綴的項目應都正確。"""
        resp = client.post("/query_spec", json={
            "product_name": "綠色圓柱",
            "inspection_items": ["外觀缺陷", "重量檢查", "顏色"],
        })
        assert resp.status_code == 200
        items = {i["name"]: i for i in resp.json()["inspection_items"]}
        assert items["外觀缺陷"]["threshold"] == 0.85
        assert items["重量檢查"]["threshold"] == 0.90
        assert items["重量檢查"]["standard"] == "120g ±5g"
        assert items["顏色"]["threshold"] == 0.90

    def test_truly_unknown_item_still_gets_default(self, client):
        """真正不存在的項目（如硬度）不應被模糊比對誤配，應回預設值。"""
        resp = client.post("/query_spec", json={
            "product_name": "藍色方塊",
            "inspection_items": ["硬度"],
        })
        assert resp.status_code == 200
        item = resp.json()["inspection_items"][0]
        assert item["threshold"] == 0.80
        assert item["standard"] == "無明顯缺陷"


# ─── 所有產品 × 所有項目 ───────────────────────────────────────────────────────

class TestAllProductSpecs:
    """每筆產品的四個 inspection_specs 都應能正確查詢。"""

    @pytest.mark.parametrize("product,item,threshold", [
        ("藍色方塊",   "外觀缺陷", 0.85),
        ("藍色方塊",   "尺寸",     0.95),
        ("藍色方塊",   "重量",     0.90),
        ("藍色方塊",   "顏色",     0.90),
        ("紅色圓球",   "外觀缺陷", 0.85),
        ("紅色圓球",   "尺寸",     0.95),
        ("紅色圓球",   "重量",     0.90),
        ("紅色圓球",   "顏色",     0.90),
        ("黃色三角形", "外觀缺陷", 0.85),
        ("黃色三角形", "尺寸",     0.95),
        ("黃色三角形", "重量",     0.90),
        ("黃色三角形", "顏色",     0.90),
        ("綠色圓柱",   "外觀缺陷", 0.85),
        ("綠色圓柱",   "尺寸",     0.95),
        ("綠色圓柱",   "重量",     0.90),
        ("綠色圓柱",   "顏色",     0.90),
        ("黑色長方體", "外觀缺陷", 0.85),
        ("黑色長方體", "尺寸",     0.95),
        ("黑色長方體", "重量",     0.90),
        ("黑色長方體", "顏色",     0.90),
    ])
    def test_spec_threshold(self, client, product, item, threshold):
        resp = client.post("/query_spec", json={
            "product_name": product,
            "inspection_items": [item],
        })
        assert resp.status_code == 200
        assert resp.json()["inspection_items"][0]["threshold"] == threshold


# ─── product_retriever 顏色形狀規則 ──────────────────────────────────────────

class TestColorShapeRule:
    @pytest.mark.parametrize("text,expected_product", [
        ("我想知道藍色方塊的重量",   "藍色方塊"),
        ("紅色圓球有沒有缺陷",       "紅色圓球"),
        ("黃色三角形的尺寸",         "黃色三角形"),
        ("綠色圓柱長什麼樣",         "綠色圓柱"),
        ("黑色長方體多重",           "黑色長方體"),
    ])
    def test_color_shape_matches_correct_product(self, text, expected_product):
        from app.command_parser import parse_command
        from app.product_retriever import retrieve_product
        parsed = parse_command(text)
        parsed["product_name"] = None  # 強制跳過 Tier 1
        result = retrieve_product(text, parsed)
        assert result is not None
        assert result["product"]["product_name"] == expected_product
        assert result["matched_by"] == "color_shape_rule"
