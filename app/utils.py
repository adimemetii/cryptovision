import json
import re
from pathlib import Path

import pandas as pd
from flask import current_app
from werkzeug.utils import secure_filename

from app.data_processing import read_dataframe


def safe_user_file(filename, suffix=None):
    clean = secure_filename(filename) or "dataset"
    stem = Path(clean).stem[:100]
    ext = suffix or Path(clean).suffix
    return f"{stem}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"


def dataset_dataframe(dataset, cleaned=True):
    filename = dataset.cleaned_path if cleaned else dataset.original_path
    path = str(Path(current_app.config["UPLOAD_FOLDER"]) / Path(filename).name)
    return read_dataframe(path, dataset.file_type if not cleaned else Path(path).suffix.lstrip("."))


def json_dumps(value):
    return json.dumps(value, default=str)


def normalize_email(email):
    return email.strip().lower()


def valid_password(password):
    return bool(password and len(password) >= 8)


def infer_entity_columns(metadata):
    candidates = []
    for column in metadata.get("categorical_columns", []):
        if re.search(r"asset|symbol|coin|collection|product|name|category", column, re.I):
            candidates.append(column)
    return candidates or metadata.get("categorical_columns", [])


def available_entity_values(dataset, column):
    if not column:
        return []
    df = dataset_dataframe(dataset)
    if column not in df.columns:
        return []
    return [str(value) for value in df[column].dropna().astype(str).drop_duplicates().head(100).tolist()]
