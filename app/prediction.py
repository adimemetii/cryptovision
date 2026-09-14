import json
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
)


def _plotly():
    try:
        import plotly.graph_objects as go

        return go
    except ImportError as exc:
        raise RuntimeError("Plotly is not installed. Install the requirements first.") from exc


def _future_dates(dates, horizon):
    dates = pd.to_datetime(dates, errors="coerce").dropna()
    if dates.empty:
        return pd.RangeIndex(start=0, stop=horizon)
    if len(dates) > 1:
        delta = dates.diff().dropna().median()
        if pd.isna(delta) or delta <= pd.Timedelta(0):
            delta = pd.Timedelta(days=1)
    else:
        delta = pd.Timedelta(days=1)
    return pd.DatetimeIndex([dates.iloc[-1] + delta * (i + 1) for i in range(horizon)])


def linear_forecast(dataframe, target_column, date_column=None, horizon=7):
    if target_column not in dataframe.columns:
        raise ValueError("Select a valid target column.")
    horizon = max(1, min(int(horizon), 365))
    work = dataframe.copy()
    dates = pd.to_datetime(work[date_column], errors="coerce") if date_column in work.columns else pd.Series(pd.NaT, index=work.index)
    work["_target"] = pd.to_numeric(work[target_column], errors="coerce")
    work = work.loc[work["_target"].notna()].copy()
    if date_column in work.columns:
        work["_date"] = dates.loc[work.index]
        work = work.loc[work["_date"].notna()].sort_values("_date")
    else:
        work["_date"] = np.arange(len(work))
    if len(work) < 5:
        raise ValueError("Not enough historical data to generate a reliable forecast.")

    values = work["_target"].to_numpy(dtype=float)
    timeline = np.arange(len(values), dtype=float).reshape(-1, 1)
    split = max(3, int(len(values) * 0.8))
    if split >= len(values):
        split = len(values) - 1
    model = LinearRegression().fit(timeline[:split], values[:split])
    holdout_pred = model.predict(timeline[split:])
    metrics = {
        "MAE": round(float(mean_absolute_error(values[split:], holdout_pred)), 6),
        "R2": round(float(r2_score(values[split:], holdout_pred)) if len(values[split:]) > 1 else 0.0, 6),
    }
    final_model = LinearRegression().fit(timeline, values)
    future_x = np.arange(len(values), len(values) + horizon, dtype=float).reshape(-1, 1)
    predictions = final_model.predict(future_x)
    historical_dates = work["_date"].tolist()
    future_dates = _future_dates(pd.Series(historical_dates), horizon) if date_column in dataframe.columns else list(range(len(values), len(values) + horizon))
    result = pd.DataFrame(
        {
            "date": historical_dates + list(future_dates),
            "actual": list(values) + [np.nan] * horizon,
            "predicted": [np.nan] * len(values) + list(predictions),
            "kind": ["Historical"] * len(values) + ["Forecast"] * horizon,
        }
    )
    go = _plotly()
    fig = go.Figure()
    fig.add_scatter(x=historical_dates, y=values, mode="lines+markers", name="Actual")
    fig.add_scatter(x=list(future_dates), y=predictions, mode="lines+markers", name="Predicted")
    fig.update_layout(template="plotly_dark", title="Linear Regression Forecast", margin=dict(l=20, r=20, t=50, b=20))
    return {"metrics": metrics, "result": result, "figure": fig}


def xgb_direction_forecast(dataframe, target_column, date_column=None, horizon=7):
    if target_column not in dataframe.columns:
        raise ValueError("Select a valid target column.")
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("XGBoost is not installed. Install the requirements first.") from exc

    work = dataframe.copy()
    if date_column in work.columns:
        work["_date"] = pd.to_datetime(work[date_column], errors="coerce")
    else:
        work["_date"] = np.arange(len(work))
    work["_target"] = pd.to_numeric(work[target_column], errors="coerce")
    work = work.loc[work["_target"].notna()].sort_values("_date").reset_index(drop=True)
    if len(work) < 15:
        raise ValueError("Not enough historical data to generate a reliable forecast.")

    numeric = work.select_dtypes(include=[np.number]).columns.tolist()
    numeric = [column for column in numeric if column not in {"_target", "_date"}]
    features = pd.DataFrame(index=work.index)
    target_values = work["_target"]
    features["lag_1"] = target_values.shift(1)
    features["lag_2"] = target_values.shift(2)
    features["lag_7"] = target_values.shift(7)
    features["rolling_mean_7"] = target_values.shift(1).rolling(7).mean()
    features["return_1"] = target_values.shift(1).pct_change()
    for column in numeric:
        features[f"feature_{column}"] = pd.to_numeric(work[column], errors="coerce")
    future_values = target_values.shift(-1)
    labels = (future_values > target_values).astype(float)
    labels.loc[future_values.isna()] = np.nan
    usable = features.replace([np.inf, -np.inf], np.nan).dropna().index.intersection(labels.dropna().index)
    features = features.loc[usable]
    labels = labels.loc[usable].astype(int)
    if labels.nunique() < 2 or len(features) < 10:
        raise ValueError("Not enough historical variation to classify UP and DOWN.")
    split = max(8, int(len(features) * 0.75))
    if split >= len(features):
        split = len(features) - 1
    X_train, X_test = features.iloc[:split], features.iloc[split:]
    y_train, y_test = labels.iloc[:split], labels.iloc[split:]
    if y_train.nunique() < 2:
        raise ValueError("Training history contains only one direction.")
    model = XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    predicted = model.predict(X_test).astype(int)
    metrics = {
        "Accuracy": round(float(accuracy_score(y_test, predicted)), 6),
        "Precision": round(float(precision_score(y_test, predicted, zero_division=0)), 6),
        "Recall": round(float(recall_score(y_test, predicted, zero_division=0)), 6),
        "F1": round(float(f1_score(y_test, predicted, zero_division=0)), 6),
        "Confusion Matrix": confusion_matrix(y_test, predicted, labels=[0, 1]).tolist(),
    }
    last_features = features.iloc[[-1]]
    final_prediction = "UP" if int(model.predict(last_features)[0]) == 1 else "DOWN"
    result = pd.DataFrame(
        {
            "date": work.loc[X_test.index, "_date"].tolist(),
            "actual_direction": ["UP" if value else "DOWN" for value in y_test],
            "predicted_direction": ["UP" if value else "DOWN" for value in predicted],
        }
    )
    go = _plotly()
    fig = go.Figure()
    fig.add_scatter(x=result["date"], y=result["predicted_direction"], mode="lines+markers", name="Predicted direction")
    fig.update_layout(template="plotly_dark", title=f"Direction Classification — Next: {final_prediction}", margin=dict(l=20, r=20, t=50, b=20))
    return {"metrics": metrics, "result": result, "figure": fig, "final_prediction": final_prediction}


def metrics_json(metrics):
    return json.dumps(metrics, default=lambda value: value.item() if hasattr(value, "item") else value)
