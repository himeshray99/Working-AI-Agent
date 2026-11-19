import json
import logging
from pathlib import Path
from typing import TypedDict, Any
import pandas as pd
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:  # Allows deterministic local smoke tests before optional deps are installed.
    StateGraph = None
    END = None
    LANGGRAPH_AVAILABLE = False

from agents.content_agent import generate_product_content
from agents.image_agent import run_image_agent
from agents.competitor_agent import research_product
from agents.sales_agent import run_sales_agent
from config import IMAGE_LIMIT, COMPETITOR_LIMIT, TAVILY_MAX_RESULTS, ENABLE_IMAGE_GENERATION, ENABLE_COMPETITOR_RESEARCH
from processing.excel_reader import read_workbook
from processing.cleaning import clean_vendor_data, clean_sales_data
from processing.validators import validate_product_content
from utils.ollama_client import OllamaClient
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

class PipelineState(TypedDict, total=False):
    input_path: str
    output_dir: str
    vendor_df: Any
    sales_df: Any
    sheet_names: list
    content_rows: list
    image_rows: list
    competitor_rows: list
    sales_summary: dict
    errors: list
    result: dict

def load_data(state: PipelineState):
    vendor, sales, names = read_workbook(state["input_path"])
    vendor = clean_vendor_data(vendor)
    sales = clean_sales_data(sales)
    logger.info("Loaded vendor rows=%s sales rows=%s sheets=%s", len(vendor), len(sales), names)
    return {"vendor_df": vendor, "sales_df": sales, "sheet_names": names}

def generate_content_node(state: PipelineState):
    llm = OllamaClient()
    rows, errors = [], []
    for _, row in state["vendor_df"].iterrows():
        source = row.to_dict()
        try:
            result = generate_product_content(source, llm)
            result["validation_issues"] = validate_product_content(result)
            rows.append(result)
        except Exception as exc:
            errors.append(f"content: {type(exc).__name__}: {exc}")
            logger.exception("Content generation failed")
    return {"content_rows": rows, "errors": state.get("errors", []) + errors}

def generate_images_node(state: PipelineState):
    output_images = Path(state["output_dir"]) / "generated_images"
    image_rows = []
    if not ENABLE_IMAGE_GENERATION:
        for _, row in state["vendor_df"].head(IMAGE_LIMIT).iterrows():
            sku = row.get("SKU", row.get("Masked SKU", "UNKNOWN"))
            image_rows.append({"sku": str(sku), "status": "skipped",
                               "reason": "ENABLE_IMAGE_GENERATION=false"})
        return {"image_rows": image_rows}
    for _, row in state["vendor_df"].head(IMAGE_LIMIT).iterrows():
        image_rows.append(run_image_agent(row.to_dict(), output_images))
    return {"image_rows": image_rows}

def competitor_node(state: PipelineState):
    if not ENABLE_COMPETITOR_RESEARCH:
        return {"competitor_rows": []}

    records, errors = [], []
    content_by_sku = {str(item.get("sku")): item for item in state.get("content_rows", [])}

    for _, row in state["vendor_df"].head(COMPETITOR_LIMIT).iterrows():
        product = row.to_dict()
        sku_value = product.get("SKU") or product.get("Masked SKU") or product.get("masked sku")
        sku = str(sku_value) if sku_value is not None else "UNKNOWN"
        content = content_by_sku.get(sku, {})
        product["sku"] = sku
        product["product_title"] = content.get("product_title") or product.get("Vendor1 Name") or sku

        try:
            product_records = research_product(product, limit=TAVILY_MAX_RESULTS)
            records.extend(product_records)
        except Exception as exc:
            errors.append(f"competitor SKU {sku}: {type(exc).__name__}: {exc}")
            logger.exception("Competitor research failed for SKU %s", sku)
            records.append({
                "sku": sku, "search_query": "", "competitor_product": "",
                "marketplace_or_website": "", "competitor_price": None, "currency": None,
                "price_difference": None, "competitive_insight": "Research failed; no competitor or price inferred.",
                "source_url": "", "price_extraction_method": "not_available",
                "research_status": f"failed: {type(exc).__name__}",
            })

    return {"competitor_rows": records, "errors": state.get("errors", []) + errors}

def sales_node(state: PipelineState):
    summary = run_sales_agent(state["sales_df"])
    return {"sales_summary": summary}

def export_node(state: PipelineState):
    out = Path(state["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    content = pd.json_normalize(state.get("content_rows", []), sep=".")
    competitors = pd.DataFrame(state.get("competitor_rows", []))
    images = pd.DataFrame(state.get("image_rows", []))
    sales = state.get("sales_summary", {})

    content.to_excel(out / "product_content.xlsx", index=False)
    competitors.to_excel(out / "competitor_analysis.xlsx", index=False)
    pd.DataFrame(sales.get("top_performing_items", [])).to_excel(out / "top_items.xlsx", index=False)
    pd.DataFrame(sales.get("low_performing_items_in_sales_file", [])).to_excel(out / "low_items.xlsx", index=False)
    images.to_excel(out / "image_generation_status.xlsx", index=False)

    with pd.ExcelWriter(out / "sales_analysis.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([{
            k: v for k, v in sales.items()
            if k not in {"top_performing_items", "low_performing_items_in_sales_file", "top_revenue_items", "monthly_sales", "sales_insights", "status_counts"}
        }]).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame([sales.get("status_counts", {})]).to_excel(writer, sheet_name="StatusCounts", index=False)
        pd.DataFrame(sales.get("top_performing_items", [])).to_excel(writer, sheet_name="TopItems", index=False)
        pd.DataFrame(sales.get("low_performing_items_in_sales_file", [])).to_excel(writer, sheet_name="LowItems", index=False)
        pd.DataFrame(sales.get("top_revenue_items", [])).to_excel(writer, sheet_name="TopRevenue", index=False)
        pd.DataFrame(sales.get("monthly_sales", [])).to_excel(writer, sheet_name="MonthlySales", index=False)
        pd.DataFrame({"insight": sales.get("sales_insights", [])}).to_excel(writer, sheet_name="Insights", index=False)

    # Consolidated workbook with independent datasets; no false SKU join is attempted.
    with pd.ExcelWriter(out / "final_report.xlsx", engine="openpyxl") as writer:
        content.to_excel(writer, sheet_name="ProductContent", index=False)
        competitors.to_excel(writer, sheet_name="Competitors", index=False)
        pd.DataFrame([{
            k: v for k, v in sales.items()
            if k not in {"top_performing_items", "low_performing_items_in_sales_file", "top_revenue_items", "monthly_sales", "sales_insights", "status_counts"}
        }]).to_excel(writer, sheet_name="SalesSummary", index=False)
        pd.DataFrame(sales.get("top_performing_items", [])).to_excel(writer, sheet_name="TopSalesItems", index=False)
        pd.DataFrame(sales.get("low_performing_items_in_sales_file", [])).to_excel(writer, sheet_name="LowSalesItems", index=False)
        pd.DataFrame(sales.get("top_revenue_items", [])).to_excel(writer, sheet_name="TopRevenueItems", index=False)
        pd.DataFrame(sales.get("monthly_sales", [])).to_excel(writer, sheet_name="MonthlySales", index=False)
        pd.DataFrame({"insight": sales.get("sales_insights", [])}).to_excel(writer, sheet_name="SalesInsights", index=False)

    summary = {
        "input_file": state["input_path"],
        "vendor_count": int(len(state["vendor_df"])),
        "sales_lines": int(len(state["sales_df"])),
        "content_count": len(state.get("content_rows", [])),
        "competitor_count": len(state.get("competitor_rows", [])),
        "images_generated": int(sum(1 for x in state.get("image_rows", []) if x.get("status") == "generated")),
        "image_statuses": state.get("image_rows", []),
        "sales_summary": sales,
        "errors": state.get("errors", []),
        "sheet_names": state.get("sheet_names", [])
    }
    (out / "execution_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return {"result": summary}

def build_graph():
    if not LANGGRAPH_AVAILABLE:
        return None
    graph = StateGraph(PipelineState)
    graph.add_node("load_data", load_data)
    graph.add_node("generate_content", generate_content_node)
    graph.add_node("generate_images", generate_images_node)
    graph.add_node("competitor_research", competitor_node)
    graph.add_node("sales_analysis", sales_node)
    graph.add_node("export_outputs", export_node)
    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "generate_content")
    graph.add_edge("generate_content", "generate_images")
    graph.add_edge("generate_images", "competitor_research")
    graph.add_edge("competitor_research", "sales_analysis")
    graph.add_edge("sales_analysis", "export_outputs")
    graph.add_edge("export_outputs", END)
    return graph.compile()

def run_pipeline(input_path: Path, output_dir: Path):
    setup_logging()
    initial = {
        "input_path": str(input_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "errors": []
    }
    app = build_graph()
    if app is not None:
        state = app.invoke(initial)
    else:
        # Sequential fallback preserves the same node order when LangGraph is not installed.
        state = initial
        for node in (load_data, generate_content_node, generate_images_node,
                     competitor_node, sales_node, export_node):
            state.update(node(state))
    return state.get("result", {})
