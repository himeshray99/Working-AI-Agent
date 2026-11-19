import pandas as pd
import pytest

from processing.excel_reader import read_workbook


def test_read_workbook_reads_two_sheets(tmp_path):
    path = tmp_path / "sample.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"SKU": ["A"]}).to_excel(writer, sheet_name="vendor data", index=False)
        pd.DataFrame({"amount": [10]}).to_excel(writer, sheet_name="sales data", index=False)

    vendor, sales, names = read_workbook(path)
    assert vendor.loc[0, "SKU"] == "A"
    assert sales.loc[0, "amount"] == 10
    assert names == ["vendor data", "sales data"]


def test_read_workbook_rejects_single_sheet(tmp_path):
    path = tmp_path / "one_sheet.xlsx"
    pd.DataFrame({"SKU": ["A"]}).to_excel(path, index=False)

    with pytest.raises(ValueError, match="Expected two sheets"):
        read_workbook(path)
