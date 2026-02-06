"""
Basic request validation: ensure JSON body and required fields.
No authentication; only structural validation for licensing APIs.
"""
from flask import jsonify, request

REQUIRED_LICENSE_FIELDS = ("license_id", "org_id", "device_id")
REQUIRED_TRIAL_FIELDS = ("device_id",)


def validate_body(required_fields):
    """Return (None, None) if valid, else (response, status_code)."""

    if not request.is_json:
        return jsonify(success=False, error="Invalid or missing JSON body"), 400
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(success=False, error="Invalid or missing JSON body"), 400
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify(success=False, error=f"Missing required fields: {', '.join(missing)}"), 400
    return None, None


def validate_license_request():
    """Use for /license/* routes. Returns (None, None) or (error_response, status)."""
    return validate_body(REQUIRED_LICENSE_FIELDS)


def validate_trial_request():
    """Use for /trial/validate. Returns (None, None) or (error_response, status)."""
    return validate_body(REQUIRED_TRIAL_FIELDS)
