def validate_product_content(record: dict) -> list[str]:
    issues = []
    if not record.get("product_title"):
        issues.append("Missing product title")
    if not record.get("product_description"):
        issues.append("Missing product description")
    features = record.get("key_features", [])
    if not isinstance(features, list):
        issues.append("key_features must be a list")
    elif len(features) > 5:
        issues.append("More than five key features")
    if record.get("generation_status") != "generated_by_local_llm":
        issues.append("Review: local LLM generation did not complete normally")
    return issues
