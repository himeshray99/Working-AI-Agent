import pandas as pd

def clean_vendor_data(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    # Clean ragged bullet cells inside the pipeline; preserve original non-empty wording.
    for col in out.columns:
        if col.lower().startswith("bullet"):
            out[col] = out[col].apply(
                lambda x: "" if pd.isna(x) else " ".join(str(x).split())
            )
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
    return out

def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
    if "orderDate" in out.columns:
        out["orderDate"] = pd.to_datetime(out["orderDate"], errors="coerce")
    for col in ("quantity", "price", "amount"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out
