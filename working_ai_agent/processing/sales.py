import re
import pandas as pd

def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())

def _find_col(columns, candidates):
    lookup = {_norm(c): c for c in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None

CANCELLED = {"cancelled", "canceled", "void", "voided"}
PENDING = {"pending", "awaiting payment", "awaiting_payment"}

def analyze_sales(df: pd.DataFrame) -> dict:
    data = df.copy()
    status_col = _find_col(data.columns, {"orderstatus", "status"})
    status_counts = {}
    if status_col:
        statuses = data[status_col].fillna("blank").astype(str).str.strip().str.lower()
        status_counts = statuses.value_counts(dropna=False).to_dict()
        cancelled_mask = statuses.isin(CANCELLED)
        pending_mask = statuses.isin(PENDING)
        included = data.loc[~(cancelled_mask | pending_mask)].copy()
    else:
        cancelled_mask = pd.Series(False, index=data.index)
        pending_mask = pd.Series(False, index=data.index)
        included = data.copy()

    qty_col = _find_col(included.columns, {"quantity", "qty", "units"})
    amount_col = _find_col(included.columns, {"amount", "salesamount", "total"})
    price_col = _find_col(included.columns, {"price", "unitprice", "sellingprice"})
    item_col = _find_col(included.columns, {"itemname", "productname", "product", "sku"})
    date_col = _find_col(included.columns, {"orderdate", "date"})
    order_col = _find_col(included.columns, {"orderid", "ordernumber"})

    if qty_col:
        included[qty_col] = pd.to_numeric(included[qty_col], errors="coerce").fillna(0)
    if amount_col:
        included[amount_col] = pd.to_numeric(included[amount_col], errors="coerce")
    if price_col:
        included[price_col] = pd.to_numeric(included[price_col], errors="coerce")

    if amount_col:
        revenue = float(included[amount_col].fillna(0).sum())
        revenue_method = "sum of provided amount column"
    elif qty_col and price_col:
        revenue = float((included[qty_col] * included[price_col]).sum())
        revenue_method = "quantity multiplied by price"
    else:
        revenue = 0.0
        revenue_method = "unavailable: amount/quantity/price columns missing"

    units = float(included[qty_col].sum()) if qty_col else 0.0
    grouped_records = []
    if item_col:
        aggregation = {}
        if qty_col:
            aggregation["units_sold"] = (qty_col, "sum")
        if amount_col:
            aggregation["sales_amount"] = (amount_col, "sum")
        if not aggregation:
            aggregation["line_count"] = (item_col, "count")
        grouped = included.groupby(item_col, dropna=False).agg(**aggregation).reset_index()
        sort_metric = "units_sold" if "units_sold" in grouped.columns else "line_count"
        top_units = grouped.sort_values(sort_metric, ascending=False).head(10)
        low_units = grouped.sort_values(sort_metric, ascending=True).head(10)
        if "sales_amount" in grouped.columns:
            top_revenue = grouped.sort_values("sales_amount", ascending=False).head(10)
        else:
            top_revenue = pd.DataFrame()
        grouped_records = grouped.to_dict(orient="records")
    else:
        top_units = low_units = top_revenue = pd.DataFrame()

    date_start = date_end = None
    monthly_sales = []
    if date_col:
        dates = pd.to_datetime(included[date_col], errors="coerce")
        if dates.notna().any():
            date_start = dates.min().date().isoformat()
            date_end = dates.max().date().isoformat()
            if amount_col:
                monthly = included.assign(_month=dates.dt.to_period("M").astype(str)).groupby("_month")[amount_col].sum()
                monthly_sales = [{"month": str(k), "sales_amount": float(v)} for k, v in monthly.items()]

    unique_orders = int(included[order_col].nunique()) if order_col else None
    unique_items = int(included[item_col].nunique()) if item_col else None
    insights = []
    if len(data):
        excluded_count = int(cancelled_mask.sum() + pending_mask.sum())
        insights.append(
            f"Excluded {excluded_count:,} of {len(data):,} source lines "
            f"({excluded_count / len(data):.1%}) for cancelled or pending status."
        )
    if not top_units.empty and "units_sold" in top_units.columns:
        first = top_units.iloc[0]
        insights.append(
            f"Highest-volume item in the sales file is {first[item_col]} "
            f"with {int(first['units_sold']):,} units."
        )
    if not top_revenue.empty:
        first = top_revenue.iloc[0]
        insights.append(
            f"Highest sales-amount item in the sales file is {first[item_col]} "
            f"with {float(first['sales_amount']):,.2f} in workbook amount units."
        )
    if monthly_sales:
        peak = max(monthly_sales, key=lambda x: x["sales_amount"])
        insights.append(
            f"Highest included monthly sales amount is {peak['month']} "
            f"({peak['sales_amount']:,.2f} in workbook amount units)."
        )
    return {
        "total_sales": revenue,
        "units_sold": units,
        "included_order_lines": int(len(included)),
        "excluded_cancelled_lines": int(cancelled_mask.sum()),
        "excluded_pending_lines": int(pending_mask.sum()),
        "status_counts": status_counts,
        "revenue_method": revenue_method,
        "date_start": date_start,
        "date_end": date_end,
        "unique_orders": unique_orders,
        "unique_items_in_sales_file": unique_items,
        "top_performing_items": top_units.to_dict(orient="records"),
        "low_performing_items_in_sales_file": low_units.to_dict(orient="records"),
        "top_revenue_items": top_revenue.to_dict(orient="records"),
        "monthly_sales": monthly_sales,
        "sales_insights": insights,
        "non_moving_sku_note": (
            "Cannot identify non-moving vendor SKUs: the vendor SKU sheet and sales item identifiers "
            "have no matching SKU values. Low-performing items are the lowest-volume items present "
            "in the sales file, not confirmed zero-sales vendor SKUs."
        ),
        "currency_note": "No currency field is supplied; sales amounts are reported in the workbook's numeric units without assuming a currency.",
        "status_filter_note": "Excluded statuses: cancelled, canceled, void, voided, pending, awaiting payment, awaiting_payment. Other statuses (including OJ Shipping) are included.",
    }
