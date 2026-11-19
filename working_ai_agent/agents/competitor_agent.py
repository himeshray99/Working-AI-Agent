import os
import re
import logging
from urllib.parse import urlparse
try:
    from tavily import TavilyClient
except ImportError:  # Allows offline unit tests; live research requires tavily-python.
    TavilyClient = None

logger = logging.getLogger(__name__)


def _client():
    if TavilyClient is None:
        raise RuntimeError("tavily-python is not installed. Run pip install -r requirements.txt.")
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TAVILY_API_KEY is missing. Add it to the local .env file.")
    return TavilyClient(api_key=key)


def _host(url):
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _price_from_text(text):
    """
    Conservative extraction: only accept amounts explicitly adjacent to a price
    label/currency marker. Reject amounts in shipping, assembly, reward and review
    contexts. Returned amounts remain unverified candidates, never confirmed prices.
    """
    text = text or ""
    patterns = [
        (r"(?:current\s+price|sale\s+price|regular\s+price|price|now)\s*[:\-]?\s*(?:USD\s*)?\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", "USD"),
        (r"\bUSD\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", "USD"),
        (r"(?:price|now|sale)\s*[:\-]?\s*(?:INR\s*)?₹\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", "INR"),
        (r"\bINR\s*₹?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", "INR"),
    ]
    excluded = re.compile(
        r"shipping|delivery|assembly|installation|reward|cashback|coupon|"
        r"discount code|per month|monthly payment|financing|review|rating",
        re.IGNORECASE,
    )
    for pattern, currency in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            context = text[max(0, match.start()-100):match.end()+100]
            if excluded.search(context):
                continue
            try:
                value = float(match.group(1).replace(",", ""))
                if value > 0:
                    return value, currency
            except ValueError:
                continue
    return None, None


def research_product(product: dict, limit: int = 3, llm=None):
    """Find competitor candidates; source evidence is retained for human verification."""
    sku = product.get("sku") or product.get("SKU") or product.get("Masked SKU") or "UNKNOWN"
    title = product.get("product_title") or product.get("Vendor1 Name") or str(sku)
    category = product.get("Category", "")
    material = product.get("Material Used", "")
    color = product.get("Color", "")
    # Search using product identity and only the most discriminative attributes.
    # Broad material lists (e.g. particle board, metal, paper) create irrelevant
    # industrial/raw-material results, so they are deliberately excluded.
    query_parts = [title, category, color]
    query = " ".join(str(x).strip() for x in query_parts
                     if x and str(x).strip())
    query = re.sub(r"\s+", " ", query).strip()
    if not query or query.lower() in {"furniture", "lilola home furniture"}:
        query = f"{category} {color} furniture product".strip()

    try:
        client = _client()
        search = client.search(
            query=query, search_depth="basic",
            max_results=max(3, min(int(limit), 5)),
            include_answer=False, include_raw_content=False,
        )
    except Exception as exc:
        logger.warning("Tavily search failed for SKU %s: %s", sku, type(exc).__name__)
        return [{
            "sku": str(sku), "search_query": query, "competitor_product": "",
            "marketplace_or_website": "", "competitor_price": None, "currency": None,
            "price_difference": None,
            "competitive_insight": "Search unavailable; no competitor or price inferred.",
            "source_url": "", "price_extraction_method": "not_available",
            "research_status": f"search_failed: {type(exc).__name__}",
            "match_quality": "not_assessed",
        }]

    candidates = search.get("results", []) or []
    if not candidates:
        return [{
            "sku": str(sku), "search_query": query, "competitor_product": "",
            "marketplace_or_website": "", "competitor_price": None, "currency": None,
            "price_difference": None, "competitive_insight": "No search candidates returned.",
            "source_url": "", "price_extraction_method": "not_available",
            "research_status": "no_results", "match_quality": "not_assessed",
        }]

    records, seen_urls = [], set()
    for item in candidates[:min(3, len(candidates))]:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title_result = item.get("title", "")
        snippet = item.get("content", "") or item.get("snippet", "")
        raw, extract_status = "", "search_snippet_only"
        if url.startswith(("https://", "http://")):
            try:
                extracted = client.extract(urls=[url], extract_depth="basic")
                extracted_results = extracted.get("results", []) or []
                if extracted_results:
                    raw = extracted_results[0].get("raw_content", "") or ""
                    extract_status = "page_extracted" if raw else "page_extraction_empty"
                else:
                    extract_status = "page_extraction_unavailable"
            except Exception as exc:
                logger.info("Tavily extraction failed for %s (%s)", url, type(exc).__name__)
                extract_status = f"page_extraction_failed: {type(exc).__name__}"

        evidence = raw or snippet
        # Only full extracted page text may populate the price column.
        price, currency = _price_from_text(raw) if raw else (None, None)
        combined = f"{title_result} {evidence}".lower()
        requested_terms = [str(x).lower().strip() for x in (category, color)
                           if x and str(x).strip()]
        matched = [term for term in requested_terms if term in combined]
        # Do not call a result a potential match based on generic material overlap.
        title_tokens = [t for t in re.findall(r"[a-z0-9]+", str(title).lower())
                        if len(t) > 3 and t not in {"benjara", "lilola", "home", "furniture"}]
        identity_hits = sum(token in combined for token in title_tokens)
        ratio = len(matched) / len(requested_terms) if requested_terms else 0
        quality = ("potential_match" if identity_hits >= 2 and ratio >= 0.5
                   else "weak_match" if identity_hits >= 1 or ratio > 0
                   else "unverified")
        records.append({
            "sku": str(sku), "search_query": query,
            "competitor_product": title_result,
            "marketplace_or_website": _host(url),
            "competitor_price": price, "currency": currency,
            "price_difference": None,
            "competitive_insight": (
                f"Research candidate only; {identity_hits} product-identity tokens and "
                f"{len(matched)}/{len(requested_terms)} category/colour attributes found. "
                "Verify the exact model, dimensions, material and listing price manually."
            ),
            "source_url": url, "search_snippet": snippet[:1200],
            "page_evidence_excerpt": evidence[:1800],
            "price_extraction_method": "contextual_full_page_text_candidate" if price is not None else "not_verified",
            "page_extraction_status": extract_status,
            "research_status": "price_candidate_requires_review" if price is not None else
                               ("page_extracted_no_verified_price" if raw else "candidate_requires_review"),
            "match_quality": quality,
            "matched_attributes": "; ".join(matched),
        })
    return records
