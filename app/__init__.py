import logging
from pathlib import Path

from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.update(config_class)
    else:
        app.config.from_object(config_class)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes import auth_bp, main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(error):
        from flask import flash, redirect, url_for

        flash("The uploaded file is too large. Maximum size is 32 MB.", "error")
        return redirect(url_for("main.upload"))

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("500.html"), 500

    with app.app_context():
        try:
            db.create_all()
        except Exception:
            logging.exception("Database initialization failed")

    return app
