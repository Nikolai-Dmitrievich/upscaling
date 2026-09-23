"""
Application entry point.
"""

import logging
import os
from pathlib import Path
from typing import Any

from flask import Flask, render_template

from app.api.views import init_routes
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory pattern."""
    base_dir = Path(__file__).resolve().parent
    app = Flask(__name__, template_folder=str(base_dir / "templates"))

    app.config["SECRET_KEY"] = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length

    init_routes(app)

    @app.errorhandler(413)
    def too_large(_error: Exception) -> tuple[Any, int]:
        """
        Werkzeug aborts the request before the view runs when MAX_CONTENT_LENGTH
        is exceeded, so the JSON error has to be produced here.
        """
        limit = settings.max_file_size_mb
        return (
            render_template("error.html", message=f"The file exceeds the allowed size {limit} MB"),
            413,
        )

    return app


if __name__ == "__main__":
    if not os.path.exists(settings.edsr_model_path):
        logger.critical("Model file not found at %s", settings.edsr_model_path)
        raise FileNotFoundError(f"Required model file not found: {settings.edsr_model_path}")

    app = create_app()
    logger.info(
        "Starting Flask app on %s:%s (debug=%s)", settings.host, settings.port, settings.debug
    )

    app.run(
        debug=settings.debug,
        host=settings.host,
        port=settings.port,
        threaded=True,
    )
