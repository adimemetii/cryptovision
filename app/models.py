import json
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    datasets = db.relationship("Dataset", backref="owner", lazy=True, cascade="all, delete-orphan")
    predictions = db.relationship("Prediction", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    original_path = db.Column(db.String(500), nullable=False)
    row_count = db.Column(db.Integer, default=0, nullable=False)
    column_count = db.Column(db.Integer, default=0, nullable=False)
    cleaned_filename = db.Column(db.String(255), nullable=False)
    cleaned_path = db.Column(db.String(500), nullable=False)
    metadata_json = db.Column(db.Text, default="{}", nullable=False)
    uploaded_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    @property
    def analysis(self):
        try:
            return json.loads(self.metadata_json or "{}")
        except (TypeError, ValueError):
            return {}


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False, index=True)
    asset_name = db.Column(db.String(255), nullable=True)
    model_type = db.Column(db.String(80), nullable=False)
    target_column = db.Column(db.String(255), nullable=False)
    date_column = db.Column(db.String(255), nullable=True)
    metrics_json = db.Column(db.Text, default="{}", nullable=False)
    prediction_file = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    dataset = db.relationship("Dataset", backref=db.backref("predictions", lazy=True))

    @property
    def metrics(self):
        try:
            return json.loads(self.metrics_json or "{}")
        except (TypeError, ValueError):
            return {}
