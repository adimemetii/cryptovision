import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app import db
from app.data_processing import (
    ALLOWED_EXTENSIONS,
    analyze_dataframe,
    clean_dataframe,
    dataframe_preview,
    read_dataframe,
    save_cleaned_dataframe,
)
from app.models import Dataset, Prediction, User
from app.prediction import linear_forecast, metrics_json, xgb_direction_forecast
from app.utils import available_entity_values, dataset_dataframe, infer_entity_columns, normalize_email, safe_user_file, valid_password
from app.visualization import CHART_DETAILS, CHART_TYPES, build_chart

auth_bp = Blueprint("auth", __name__)
main_bp = Blueprint("main", __name__)


def _owned_dataset(dataset_id):
    return Dataset.query.filter_by(id=dataset_id, user_id=current_user.id).first_or_404()


def _owned_prediction(prediction_id):
    return Prediction.query.filter_by(id=prediction_id, user_id=current_user.id).first_or_404()


@main_bp.app_context_processor
def inject_globals():
    return {"chart_types": CHART_TYPES}


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(or_(User.email == identity, User.username == identity)).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("main.dashboard"))
        flash("Invalid username/email or password.", "error")
    return render_template("auth.html", mode="login")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not all([first_name, last_name, username, email, password]):
            flash("Please complete every field.", "error")
        elif not valid_password(password):
            flash("Password must contain at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter(or_(User.username == username, User.email == email)).first():
            flash("That username or email is already registered.", "error")
        else:
            user = User(first_name=first_name, last_name=last_name, username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to CryptoVision.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth.html", mode="signup")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    datasets = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.uploaded_at.desc()).all()
    predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.created_at.desc()).all()
    return render_template(
        "dashboard.html",
        datasets=datasets[:5],
        predictions=predictions[:5],
        total_datasets=len(datasets),
        total_rows=sum(dataset.row_count for dataset in datasets),
        total_predictions=len(predictions),
        total_visualizations=0,
    )


@main_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose a CSV, Excel, or JSON file.", "error")
            return redirect(url_for("main.upload"))
        if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
            flash("Only CSV, XLSX, XLS, and JSON files are supported.", "error")
            return redirect(url_for("main.upload"))
        extension = file.filename.rsplit(".", 1)[1].lower()
        token = uuid.uuid4().hex
        original_name = secure_filename(file.filename) or f"dataset.{extension}"
        stored_original = f"{token}_{original_name}"
        original_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_original)
        file.save(original_path)
        # Power BI receives a consistent Excel export, regardless of the upload format.
        cleaned_name = f"{token}_cleaned.xlsx"
        cleaned_path = os.path.join(current_app.config["UPLOAD_FOLDER"], cleaned_name)
        try:
            original = read_dataframe(original_path, extension)
            cleaned = clean_dataframe(original)
            metadata = analyze_dataframe(original, cleaned)
            save_cleaned_dataframe(cleaned, cleaned_path)
        except Exception as exc:
            for path in (original_path, cleaned_path):
                if os.path.exists(path):
                    os.remove(path)
            flash(f"This file could not be processed: {exc}", "error")
            return redirect(url_for("main.upload"))
        dataset = Dataset(
            user_id=current_user.id,
            name=Path(original_name).stem,
            original_filename=original_name,
            file_type=extension.upper(),
            original_path=stored_original,
            row_count=metadata["rows"],
            column_count=len(metadata["columns"]),
            cleaned_filename=cleaned_name,
            cleaned_path=cleaned_name,
            metadata_json=json.dumps(metadata, default=str),
        )
        db.session.add(dataset)
        db.session.commit()
        flash("Dataset uploaded, cleaned, and analyzed successfully.", "success")
        return redirect(url_for("main.dataset_detail", dataset_id=dataset.id))
    return render_template("upload.html")


@main_bp.route("/datasets")
@login_required
def datasets():
    items = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.uploaded_at.desc()).all()
    return render_template("datasets.html", datasets=items)


@main_bp.route("/visualizations")
@login_required
def visualization_hub():
    items = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.uploaded_at.desc()).all()
    return render_template(
        "visualizations_index.html",
        datasets=items,
        chart_types=CHART_TYPES,
        chart_details=CHART_DETAILS,
    )


@main_bp.route("/powerbi")
@login_required
def powerbi():
    items = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.uploaded_at.desc()).all()
    return render_template("powerbi.html", datasets=items)


@main_bp.route("/dataset/<int:dataset_id>")
@login_required
def dataset_detail(dataset_id):
    dataset = _owned_dataset(dataset_id)
    df = dataset_dataframe(dataset)
    headers, preview_rows = dataframe_preview(df)
    return render_template("dataset_detail.html", dataset=dataset, metadata=dataset.analysis, headers=headers, preview_rows=preview_rows)


@main_bp.route("/dataset/<int:dataset_id>/download/<kind>")
@login_required
def download_dataset(dataset_id, kind):
    dataset = _owned_dataset(dataset_id)
    if kind not in {"original", "cleaned"}:
        return render_template("404.html"), 404
    if kind == "original":
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"],
            Path(dataset.original_path).name,
            as_attachment=True,
            download_name=dataset.original_filename,
        )

    cleaned_path = Path(dataset.cleaned_path)
    if cleaned_path.suffix.lower() == ".xlsx":
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"],
            cleaned_path.name,
            as_attachment=True,
            download_name=dataset.cleaned_filename,
        )

    # Convert older cleaned files created before the Excel-only export was added.
    cleaned_frame = dataset_dataframe(dataset)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        cleaned_frame.to_excel(writer, index=False)
    output.seek(0)
    download_name = f"{Path(dataset.original_filename).stem}_cleaned.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=download_name,
    )


@main_bp.route("/visualizations/<int:dataset_id>", methods=["GET", "POST"])
@login_required
def visualizations(dataset_id):
    dataset = _owned_dataset(dataset_id)
    df = dataset_dataframe(dataset)
    columns = [str(col) for col in df.columns]
    chart_json = None
    error = None
    settings = {"chart_type": "line", "x": columns[0] if columns else "", "y": "", "color": "", "aggregation": "none"}
    if request.method == "POST":
        settings.update({key: request.form.get(key, "") for key in settings})
        try:
            figure = build_chart(df, settings["chart_type"], settings["x"], settings["y"], settings["color"], settings["aggregation"])
            chart_json = figure.to_json()
        except Exception as exc:
            error = str(exc)
    return render_template(
        "visualizations.html",
        dataset=dataset,
        columns=columns,
        settings=settings,
        chart_json=chart_json,
        chart_error=error,
        chart_details=CHART_DETAILS,
    )


@main_bp.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():
    datasets = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.name.asc()).all()
    selected_dataset = None
    selected_df = None
    selected_id = request.form.get("dataset_id", type=int) or request.args.get("dataset_id", type=int)
    if selected_id:
        selected_dataset = next((item for item in datasets if item.id == selected_id), None)
    if selected_dataset is None and datasets:
        selected_dataset = datasets[0]
    if selected_dataset:
        selected_df = dataset_dataframe(selected_dataset)
    error = None
    output = None
    if request.method == "POST":
        try:
            if not selected_dataset or selected_df is None:
                raise ValueError("Upload a dataset before running a prediction.")
            entity_column = request.form.get("entity_column", "")
            entity_value = request.form.get("entity_value", "")
            if entity_column and entity_value and entity_column in selected_df.columns:
                selected_df = selected_df[selected_df[entity_column].astype(str) == entity_value].copy()
            date_column = request.form.get("date_column", "")
            target_column = request.form.get("target_column", "")
            model_type = request.form.get("model", "linear")
            horizon = request.form.get("horizon", 7, type=int) or 7
            if model_type == "linear":
                output = linear_forecast(selected_df, target_column, date_column, horizon)
            elif model_type == "xgboost":
                output = xgb_direction_forecast(selected_df, target_column, date_column, horizon)
            else:
                raise ValueError("Invalid model selection.")
            file_name = f"prediction_{uuid.uuid4().hex}.xlsx"
            file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], file_name)
            output["result"].to_excel(file_path, index=False)
            prediction_record = Prediction(
                user_id=current_user.id,
                dataset_id=selected_dataset.id,
                asset_name=entity_value or None,
                model_type="XGBoost Classification" if model_type == "xgboost" else "Linear Regression",
                target_column=target_column,
                date_column=date_column or None,
                metrics_json=metrics_json(output["metrics"]),
                prediction_file=file_name,
            )
            db.session.add(prediction_record)
            db.session.commit()
            output["prediction_id"] = prediction_record.id
            output["figure_json"] = output["figure"].to_json()
        except Exception as exc:
            db.session.rollback()
            error = str(exc)
    metadata = selected_dataset.analysis if selected_dataset else {}
    entity_columns = infer_entity_columns(metadata)
    entity_values = available_entity_values(selected_dataset, entity_columns[0]) if selected_dataset and entity_columns else []
    return render_template(
        "prediction.html",
        datasets=datasets,
        selected_dataset=selected_dataset,
        metadata=metadata,
        entity_columns=entity_columns,
        entity_values=entity_values,
        output=output,
        error=error,
    )


@main_bp.route("/prediction/download/<int:prediction_id>")
@login_required
def download_prediction(prediction_id):
    prediction_record = _owned_prediction(prediction_id)
    if not prediction_record.prediction_file:
        return render_template("404.html"), 404
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], Path(prediction_record.prediction_file).name, as_attachment=True, download_name="CryptoVision_Predictions.xlsx")


@main_bp.route("/history")
@login_required
def history():
    predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.created_at.desc()).all()
    return render_template("history.html", predictions=predictions)


@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
        current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html")


def _demo_frames():
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    crypto = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "asset": ["BTC"] * 30 + ["ETH"] * 30,
            "open": [100 + i * 1.2 for i in range(30)] + [50 + i * 0.7 for i in range(30)],
            "high": [102 + i * 1.2 for i in range(30)] + [52 + i * 0.7 for i in range(30)],
            "low": [98 + i * 1.2 for i in range(30)] + [48 + i * 0.7 for i in range(30)],
            "close": [101 + i * 1.2 for i in range(30)] + [51 + i * 0.7 for i in range(30)],
            "volume": [1000 + i * 25 for i in range(30)] + [700 + i * 18 for i in range(30)],
        }
    )
    nft = pd.DataFrame(
        {
            "date": dates,
            "collection": ["CryptoPunks", "ArtBlocks", "Metaverse"] * 10,
            "floor_price": [10 + (i % 7) * 1.5 for i in range(30)],
            "sales": [20 + i * 2 for i in range(30)],
            "volume": [300 + i * 15 for i in range(30)],
            "owners": [1000 + i * 10 for i in range(30)],
        }
    )
    return {"crypto_prices": crypto, "nft_collections": nft}


@main_bp.route("/templates")
@login_required
def templates():
    return render_template("templates.html")


@main_bp.route("/templates/download/<name>.<extension>")
@login_required
def download_template(name, extension):
    frames = _demo_frames()
    if name not in frames or extension not in {"csv", "xlsx", "json"}:
        return render_template("404.html"), 404
    frame = frames[name]
    output = io.BytesIO()
    if extension == "csv":
        output.write(frame.to_csv(index=False).encode("utf-8"))
        mimetype = "text/csv"
    elif extension == "json":
        output.write(frame.to_json(orient="records", date_format="iso", indent=2).encode("utf-8"))
        mimetype = "application/json"
    else:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=f"{name}.{extension}")


@main_bp.route("/api/dataset/<int:dataset_id>/columns")
@login_required
def dataset_columns(dataset_id):
    dataset = _owned_dataset(dataset_id)
    return jsonify({"columns": dataset.analysis.get("columns", []), "numeric": dataset.analysis.get("numeric_columns", [])})


@main_bp.route("/api/dataset/<int:dataset_id>/values")
@login_required
def dataset_values(dataset_id):
    dataset = _owned_dataset(dataset_id)
    column = request.args.get("column", "")
    return jsonify({"values": available_entity_values(dataset, column)})
