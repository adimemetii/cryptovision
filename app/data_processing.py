import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "json"}
PREVIEW_ROWS = 50


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def read_dataframe(path, file_type=None):
    suffix = (file_type or Path(path).suffix.lstrip(".")).lower()
    if suffix == "csv":
        return pd.read_csv(path)
    if suffix in {"xlsx", "xls"}:
        return pd.read_excel(path)
    if suffix == "json":
        try:
            return pd.read_json(path)
        except (ValueError, TypeError):
            with open(path, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
            if isinstance(payload, list):
                return pd.json_normalize(payload)
            if isinstance(payload, dict):
                return pd.json_normalize(payload)
            raise ValueError("JSON must contain an object or array of objects.")
    raise ValueError("Unsupported file type.")


def _safe_column_name(value):
    return str(value).strip() or "unnamed_column"


def _is_date_column(series, name):
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return False
    non_empty = series.dropna().astype(str).str.strip()
    if non_empty.empty:
        return False
    name_hint = bool(re.search(r"date|time|timestamp|day|month|year", name, re.I))
    try:
        parsed = pd.to_datetime(non_empty, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(non_empty, errors="coerce")
    coverage = parsed.notna().mean()
    return coverage >= (0.55 if name_hint else 0.85)


def clean_dataframe(dataframe):
    if dataframe is None or dataframe.empty:
        raise ValueError("The file contains no rows.")
    df = dataframe.copy()
    df.columns = [_safe_column_name(col) for col in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()].copy()

    for column in df.columns:
        if pd.api.types.is_object_dtype(df[column]) or pd.api.types.is_string_dtype(df[column]):
            df[column] = df[column].map(lambda value: value.strip() if isinstance(value, str) else value)

    for column in list(df.columns):
        if _is_date_column(df[column], str(column)):
            df[column] = pd.to_datetime(df[column], errors="coerce")
            continue
        if pd.api.types.is_object_dtype(df[column]) or pd.api.types.is_string_dtype(df[column]):
            non_empty = df[column].dropna().astype(str).str.replace(",", "", regex=False).str.strip()
            if not non_empty.empty:
                converted = pd.to_numeric(non_empty, errors="coerce")
                if converted.notna().mean() >= 0.8:
                    df[column] = pd.to_numeric(
                        df[column].astype(str).str.replace(",", "", regex=False), errors="coerce"
                    )

    df = df.drop_duplicates().reset_index(drop=True)
    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            median = df[column].median()
            if pd.notna(median):
                df[column] = df[column].fillna(median)
        elif pd.api.types.is_datetime64_any_dtype(df[column]):
            # Invalid dates remain null because inventing a date would corrupt the data.
            continue
        else:
            mode = df[column].mode(dropna=True)
            if not mode.empty:
                df[column] = df[column].fillna(mode.iloc[0])
            else:
                df[column] = df[column].fillna("Unknown")
    return df


def _json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    return value


def analyze_dataframe(original, cleaned):
    numeric = [str(col) for col in cleaned.select_dtypes(include=[np.number]).columns]
    date_columns = [str(col) for col in cleaned.columns if pd.api.types.is_datetime64_any_dtype(cleaned[col])]
    categorical = [str(col) for col in cleaned.columns if str(col) not in numeric and str(col) not in date_columns]
    crypto_terms = {"price", "close", "closing", "floor", "volume", "market", "asset", "symbol", "collection"}
    crypto_columns = [
        str(col) for col in cleaned.columns if any(term in str(col).lower() for term in crypto_terms)
    ]
    unique_values = {}
    for column in cleaned.columns:
        values = cleaned[column].dropna().unique()[:20]
        unique_values[str(column)] = [_json_value(value) for value in values]
    metadata = {
        "rows": int(len(original)),
        "columns": [str(col) for col in cleaned.columns],
        "numeric_columns": numeric,
        "categorical_columns": categorical,
        "date_columns": date_columns,
        "missing_values": int(original.isna().sum().sum()),
        "missing_by_column": {str(k): int(v) for k, v in original.isna().sum().items()},
        "duplicate_rows": int(original.duplicated().sum()),
        "unique_values": unique_values,
        "data_types": {str(k): str(v) for k, v in cleaned.dtypes.items()},
        "crypto_columns": crypto_columns,
        "crypto_enabled": bool(crypto_columns),
        "kpis": calculate_crypto_kpis(cleaned),
    }
    return metadata


def calculate_crypto_kpis(dataframe):
    """Return only crypto KPIs that can be calculated from the supplied frame."""
    normalized = {re.sub(r"[^a-z0-9]", "", str(column).lower()): column for column in dataframe.columns}
    price_column = next(
        (normalized[key] for key in ("close", "price", "closingprice", "floorprice") if key in normalized),
        None,
    )
    volume_column = next(
        (normalized[key] for key in ("volume", "tradingvolume", "salesvolume") if key in normalized),
        None,
    )
    work = dataframe.copy()
    date_columns = [column for column in work.columns if pd.api.types.is_datetime64_any_dtype(work[column])]
    if date_columns:
        work = work.sort_values(date_columns[0])
    kpis = {}
    if price_column:
        values = pd.to_numeric(work[price_column], errors="coerce").dropna()
        if not values.empty:
            kpis["Latest Price"] = round(float(values.iloc[-1]), 6)
            kpis["Highest Price"] = round(float(values.max()), 6)
            kpis["Lowest Price"] = round(float(values.min()), 6)
            kpis["Average Price"] = round(float(values.mean()), 6)
            if len(values) > 1 and values.iloc[0] != 0:
                kpis["Price Change %"] = round(float((values.iloc[-1] - values.iloc[0]) / abs(values.iloc[0]) * 100), 4)
            returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
            if not returns.empty:
                kpis["Volatility"] = round(float(returns.std() * 100), 4)
    if volume_column:
        volume = pd.to_numeric(work[volume_column], errors="coerce").dropna()
        if not volume.empty:
            kpis["Total Volume"] = round(float(volume.sum()), 6)
    entity_column = next(
        (column for key, column in normalized.items() if key in {"asset", "symbol", "collection"}),
        None,
    )
    if entity_column:
        kpis["Number of Assets"] = int(work[entity_column].nunique(dropna=True))
    return kpis


def dataframe_preview(dataframe, limit=PREVIEW_ROWS):
    preview = dataframe.head(limit).copy()
    preview = preview.replace({np.nan: None})
    headers = [str(col) for col in preview.columns]
    rows = [[_json_value(value) for value in row] for row in preview.itertuples(index=False, name=None)]
    return headers, rows


def save_cleaned_dataframe(dataframe, path):
    suffix = Path(path).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        dataframe.to_excel(path, index=False)
    elif suffix == ".json":
        dataframe.to_json(path, orient="records", date_format="iso")
    else:
        dataframe.to_csv(path, index=False)


def get_numeric_frame(dataframe):
    frame = dataframe.select_dtypes(include=[np.number]).copy()
    return frame.replace([np.inf, -np.inf], np.nan)
