import json
import re
from typing import Any
from utils.ollama_client import OllamaClient

def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:  # NaN
            return ""
    except Exception:
        pass
    return str(value).strip()

def vendor_row_to_source(row: dict) -> dict:
    bullets = []
    for key, value in row.items():
        if str(key).strip().lower().startswith("bullet"):
            text = _clean(value)
            if text:
                bullets.append(text)
    attrs = {}
    for key, value in row.items():
        k = str(key).strip()
        if k and k.lower() not in {"bullet " + str(i) for i in range(1, 21)}:
            v = _clean(value)
            if v:
                attrs[k] = v
    return {"attributes": attrs, "vendor_bullets": bullets}

def generate_product_content(row: dict, llm: OllamaClient) -> dict:
    source = vendor_row_to_source(row)
    sku = _clean(row.get("SKU") or row.get("Masked SKU") or row.get("masked sku")) or "UNKNOWN"
    prompt = f"""
You are an e-commerce product content specialist. Use ONLY the facts in the source data.
Do not invent dimensions, materials, mechanisms, warranties, certifications, compatibility,
performance claims, or included accessories. If a fact is absent, omit it or mark it unavailable.
Return valid JSON only with keys: product_title, product_description, key_features (exactly
5 concise strings when evidence permits; use fewer if fewer facts exist), important_attributes
(object), source_grounding_notes (array), missing_information (array).
Write marketplace-ready, complete sentences. Avoid placeholders and unsupported superlatives.
SKU: {sku}
SOURCE DATA:
{json.dumps(source, ensure_ascii=False)}
"""
    try:
        result = llm.chat_json(prompt)
        result["sku"] = sku
        result["generation_status"] = "generated_by_local_llm"
        result["source_bullets_used"] = source["vendor_bullets"]
        return result
    except Exception as exc:
        # Safe extractive fallback: no unsupported claims.
        attrs = source["attributes"]
        brand = _clean(attrs.get("Brand"))
        color = _clean(attrs.get("Color"))
        first_bullet = source["vendor_bullets"][0] if source["vendor_bullets"] else ""
        descriptor = re.sub(r"^one\s+", "", first_bullet, flags=re.IGNORECASE).strip()
        descriptor = descriptor.rstrip(".")
        title_parts = [brand, descriptor]
        if color:
            title_parts.append(f"— {color}")
        product_title = " ".join(part for part in title_parts if part).strip() or sku
        description_parts = source["vendor_bullets"][:]
        if not description_parts:
            description_parts = [f"{product_title} is listed in the supplied vendor data."]
        features = source["vendor_bullets"][:5]
        important_attributes = {}
        for key, value in attrs.items():
            key_lower = key.lower()
            if key_lower.startswith("ship ") or key_lower.startswith("image url"):
                continue
            if key_lower.startswith("bullet"):
                continue
            if value:
                important_attributes[key] = value
        return {
            "sku": sku,
            "product_title": product_title,
            "product_description": " ".join(description_parts),
            "key_features": features,
            "important_attributes": important_attributes,
            "source_grounding_notes": ["Extractive fallback used; review before marketplace publication."],
            "missing_information": ["Local LLM unavailable or returned invalid JSON."],
            "source_bullets_used": source["vendor_bullets"],
            "generation_status": f"fallback: {type(exc).__name__}"
        }
