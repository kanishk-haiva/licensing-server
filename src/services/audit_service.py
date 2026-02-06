"""
Optional audit logging. Writes to audit_log table for compliance/debugging.
Failures are logged but do not fail the request.
"""
import json
import logging

import db

logger = logging.getLogger(__name__)


def get_client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.remote_addr or None


def audit(request, action, entity_type, entity_id, payload):
    client_ip = get_client_ip(request)
    payload_str = json.dumps(payload) if payload and payload else None
    try:
        db.execute(
            "INSERT INTO audit_log (action, entity_type, entity_id, payload, client_ip) VALUES (%s, %s, %s, %s, %s)",
            (action, entity_type or None, entity_id or None, payload_str, client_ip),
        )
    except Exception as e:
        logger.exception("audit: failed to write audit_log: %s", e)
