import os
from unittest.mock import patch

from agents import competitor_agent as agent


class FakeTavilyClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.last_query = None

    def search(self, **kwargs):
        self.last_query = kwargs["query"]
        return {
            "results": [{
                "url": "https://www.example.com/product/123",
                "title": "Oak Wood Console Table",
                "content": "Search snippet mentions $999.",
            }]
        }

    def extract(self, **kwargs):
        return {
            "results": [{
                "raw_content": (
                    "Oak Wood Console Table. Category: Console Tables. "
                    "Color: Natural. Price: $499.00"
                )
            }]
        }


def test_usd_price_extraction():
    assert agent._price_from_text("Price: $499.00") == (499.0, "USD")


def test_inr_price_extraction():
    assert agent._price_from_text("Price: ₹12,499") == (12499.0, "INR")


def test_shipping_amount_is_not_accepted():
    assert agent._price_from_text("Shipping: $49.00") == (None, None)


def test_query_whitespace_is_normalized():
    fake = FakeTavilyClient("test-key")
    with patch.object(agent, "TavilyClient", return_value=fake), \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        agent.research_product({
            "sku": "SKU-1",
            "product_title": "Oak   Wood   Console Table",
            "Category": "Console Tables",
            "Color": "Natural",
        })
    assert fake.last_query == "Oak Wood Console Table Console Tables Natural"


def test_price_is_not_extracted_from_search_snippet_only():
    class SnippetOnlyClient(FakeTavilyClient):
        def extract(self, **kwargs):
            return {"results": [{"raw_content": ""}]}

    with patch.object(agent, "TavilyClient", return_value=SnippetOnlyClient("test-key")), \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        rows = agent.research_product({
            "sku": "SKU-1",
            "product_title": "Oak Wood Console Table",
            "Category": "Console Tables",
            "Color": "Natural",
        })
    assert len(rows) == 1
    assert rows[0]["competitor_price"] is None
    assert rows[0]["price_extraction_method"] == "not_verified"


def test_mocked_research_candidate():
    with patch.object(agent, "TavilyClient", return_value=FakeTavilyClient("test-key")), \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        rows = agent.research_product({
            "sku": "SKU-1",
            "product_title": "Oak Wood Console Table",
            "Category": "Console Tables",
            "Color": "Natural",
        })
    assert len(rows) == 1
    assert rows[0]["competitor_price"] == 499.0
    assert rows[0]["currency"] == "USD"
    assert rows[0]["marketplace_or_website"] == "example.com"
    assert rows[0]["research_status"] == "price_candidate_requires_review"
