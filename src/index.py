"""
Licensing server entry point. REST API; run behind HTTPS in production.
Uses local MySQL database (default: largon). Run from project root: python src/index.py
"""
import logging
import sys

from flask import Flask, jsonify

import config
import db
from routes.license_routes import blueprint as license_bp
from routes.trial_routes import blueprint as trial_bp

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

app.register_blueprint(license_bp, url_prefix="/license")
app.register_blueprint(trial_bp, url_prefix="/trial")


@app.route("/")
def root():
    """Root: simple response so GET / does not 404."""
    return jsonify(
        service="lic-server",
        status="ok",
        health="/health",
        endpoints=["POST /license/validate", "POST /license/heartbeat", "POST /license/release", "POST /trial/validate"],
    ), 200


@app.route("/favicon.ico")
def favicon():
    """Avoid 404 for browser favicon requests."""
    return "", 204


@app.route("/health")
def health():
    return jsonify(status="ok", service="lic-server")


@app.errorhandler(404)
def not_found(_e):
    return jsonify(success=False, error="Not found"), 404


def main():
    try:
        db.get_connection().close()
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        sys.exit(1)
    app.run(host="0.0.0.0", port=config.PORT, debug=(config.NODE_ENV == "development"))


if __name__ == "__main__":
    main()
