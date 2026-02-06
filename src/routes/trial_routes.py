"""
Trial API: validate (optional). Behavior depends on TRIAL_DURATION_SECONDS config.
"""
import logging

from flask import Blueprint, jsonify, request

from middleware.validate_request import validate_trial_request
from services import trial_service

logger = logging.getLogger(__name__)

blueprint = Blueprint("trial", __name__)


@blueprint.post("/validate")
def validate():
    err, status = validate_trial_request()
    if err is not None:
        return err, status
    try:
        result = trial_service.validate_trial(request)
        return jsonify(result), 200 if result.get("success") else 403
    except Exception as e:
        logger.exception("trial/validate: %s", e)
        return jsonify(success=False, error="Internal server error"), 500
