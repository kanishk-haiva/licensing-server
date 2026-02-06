"""
Trial validation: one trial per device, time-bound if TRIAL_DURATION_SECONDS > 0.
"""
import json
from datetime import datetime, timezone

import config
import db
from services.audit_service import audit, get_client_ip

TRIAL_DURATION_MS = config.TRIAL_DURATION_SECONDS * 1000 if config.TRIAL_DURATION_SECONDS > 0 else None


def _now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def upsert_device(device_id, org_id, metadata, set_trial_used):
    """Insert or update device. set_trial_used=True sets trial_used_at on first use; False leaves existing."""
    now_str = _now_str()
    meta_str = json.dumps(metadata) if metadata else None
    trial_used_at = now_str if set_trial_used else None
    db.execute(
        """
        INSERT INTO devices (device_id, org_id, first_seen_at, last_seen_at, trial_used_at, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          last_seen_at = VALUES(last_seen_at),
          metadata = COALESCE(VALUES(metadata), metadata),
          trial_used_at = COALESCE(devices.trial_used_at, VALUES(trial_used_at)),
          org_id = COALESCE(devices.org_id, VALUES(org_id))
        """,
        (device_id, org_id or None, now_str, now_str, trial_used_at, meta_str),
    )


def validate_trial(request):
    """Validate or start trial for device. Returns dict with success, error?, trial_active?, expires_at?."""
    data = request.get_json() or {}
    device_id = data.get("device_id")
    org_id = data.get("org_id")
    metadata = {
        "hostname": data.get("hostname"),
        "os": data.get("os"),
        "app_version": data.get("app_version"),
    }
    now_ts = datetime.now(timezone.utc).timestamp() * 1000

    device = db.query_one(
        "SELECT device_id, first_seen_at, last_seen_at, trial_used_at FROM devices WHERE device_id = %s LIMIT 1",
        (device_id,),
    )

    if not device:
        upsert_device(device_id, org_id, metadata, set_trial_used=True)
        audit(request, "trial_start", "device", device_id, {"org_id": org_id})
        expires_at = datetime.fromtimestamp((now_ts + TRIAL_DURATION_MS) / 1000, tz=timezone.utc).isoformat() if TRIAL_DURATION_MS else None
        return {"success": True, "trial_active": True, "first_use": True, "expires_at": expires_at}

    trial_start_dt = device["trial_used_at"] or device["first_seen_at"]
    if hasattr(trial_start_dt, "timestamp"):
        if getattr(trial_start_dt, "tzinfo", None) is None:
            trial_start_dt = trial_start_dt.replace(tzinfo=timezone.utc)
        trial_start_ts = trial_start_dt.timestamp() * 1000
    else:
        trial_start_ts = datetime.fromisoformat(str(trial_start_dt).replace("Z", "+00:00")).timestamp() * 1000

    if TRIAL_DURATION_MS and (now_ts - trial_start_ts) >= TRIAL_DURATION_MS:
        upsert_device(device_id, org_id, metadata, set_trial_used=False)
        audit(request, "trial_validate_fail", "device", device_id, {"reason": "trial_expired"})
        return {"success": False, "error": "Trial has expired", "trial_active": False}

    upsert_device(device_id, org_id, metadata, set_trial_used=not device["trial_used_at"])
    expires_at = datetime.fromtimestamp((trial_start_ts + TRIAL_DURATION_MS) / 1000, tz=timezone.utc).isoformat() if TRIAL_DURATION_MS else None
    return {"success": True, "trial_active": True, "first_use": False, "expires_at": expires_at}
