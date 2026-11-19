import pandas as pd

from processing.sales import analyze_sales


def test_sales_status_filter_and_totals():
    df = pd.DataFrame({
        "orderStatus": ["Processed", "OJ Shipping", "Cancelled", "Pending"],
        "quantity": [2, 3, 5, 7],
        "amount": [20.0, 30.0, 50.0, 70.0],
        "itemName": ["A", "B", "C", "D"],
        "orderId": [1, 2, 3, 4],
        "orderDate": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
    })
    result = analyze_sales(df)
    assert result["total_sales"] == 50.0
    assert result["units_sold"] == 5.0
    assert result["included_order_lines"] == 2
    assert result["excluded_cancelled_lines"] == 1
    assert result["excluded_pending_lines"] == 1


def test_sales_does_not_assume_currency():
    df = pd.DataFrame({
        "quantity": [1],
        "amount": [125.5],
        "itemName": ["A"],
    })
    result = analyze_sales(df)
    assert result["total_sales"] == 125.5
    assert "No currency field" in result["currency_note"]


def test_sales_handles_missing_status_column():
    df = pd.DataFrame({"quantity": [2], "price": [10], "itemName": ["A"]})
    result = analyze_sales(df)
    assert result["total_sales"] == 20.0
    assert result["units_sold"] == 2.0
    assert result["included_order_lines"] == 1
