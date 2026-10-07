from flask import Flask
from config import Config
from models import db
from utils.logging_config import setup_logging


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    logging_listener = setup_logging(app)
    app.extensions["log_listener"] = logging_listener

    from routes.main import main_bp
    from routes.research import research_bp
    from routes.manage import manage_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(manage_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
