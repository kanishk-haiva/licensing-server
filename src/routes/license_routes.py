"""
License API: validate, heartbeat, release.
"""
import logging

from flask import Blueprint, jsonify, request

from middleware.validate_request import validate_license_request
from services import license_service

logger = logging.getLogger(__name__)

blueprint = Blueprint("license", __name__)


@blueprint.post("/validate")
def validate():
    err, status = validate_license_request()
    if err is not None:
        return err, status
    try:
        result = license_service.validate(request)
        return jsonify(result), 200 if result.get("success") else 403
    except Exception as e:
        logger.exception("license/validate: %s", e)
        return jsonify(success=False, error="Internal server error"), 500


@blueprint.post("/heartbeat")
def heartbeat():
    err, status = validate_license_request()
    if err is not None:
        return err, status
    try:
        result = license_service.heartbeat(request)
        return jsonify(result), 200 if result.get("success") else 403
    except Exception as e:
        logger.exception("license/heartbeat: %s", e)
        return jsonify(success=False, error="Internal server error"), 500


@blueprint.post("/release")
def release():
    err, status = validate_license_request()
    if err is not None:
        return err, status
    try:
        result = license_service.release(request)
        return jsonify(result), 200 if result.get("success") else 404
    except Exception as e:
        logger.exception("license/release: %s", e)
        return jsonify(success=False, error="Internal server error"), 500
