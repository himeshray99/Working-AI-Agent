import pandas as pd

def read_workbook(path):
    workbook = pd.ExcelFile(path)
    if len(workbook.sheet_names) < 2:
        raise ValueError("Expected two sheets: vendor data and sales data")
    vendor = pd.read_excel(path, sheet_name=workbook.sheet_names[0])
    sales = pd.read_excel(path, sheet_name=workbook.sheet_names[1])
    vendor.columns = [str(c).strip() for c in vendor.columns]
    sales.columns = [str(c).strip() for c in sales.columns]
    return vendor, sales, workbook.sheet_names
