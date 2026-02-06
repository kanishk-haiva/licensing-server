"""
License validation, seat allocation, heartbeat, and release.
All timing uses last_heartbeat_at vs HEARTBEAT_TTL to decide if a seat is "active".
"""
from datetime import datetime, timezone

import config
import db
from services.audit_service import audit, get_client_ip

HEARTBEAT_TTL_MS = config.HEARTBEAT_TTL_SECONDS * 1000


def _now():
    return datetime.now(timezone.utc)


def _ensure_utc(dt):
    """Assume naive datetimes from DB are UTC for comparison."""
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _now_str():
    return _now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def is_allocation_active(last_heartbeat_at):
    """True if last_heartbeat_at is within TTL."""
    if not last_heartbeat_at:
        return False
    if hasattr(last_heartbeat_at, "timestamp"):
        # PyMySQL returns DATETIME as *naive* datetime (no tzinfo). Treat as UTC.
        dt = last_heartbeat_at
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ts = dt.timestamp()
    else:
        ts = datetime.fromisoformat(str(last_heartbeat_at).replace("Z", "+00:00")).timestamp()
    return (datetime.now(timezone.utc).timestamp() - ts) * 1000 < HEARTBEAT_TTL_MS


def validate(request):
    """Validate license and allocate or reattach seat for device. Returns dict with success, error?, allocation?."""
    data = request.get_json() or {}
    license_key = data.get("license_id")
    org_id = data.get("org_id")
    device_id = data.get("device_id")
    hostname = data.get("hostname")
    os_name = data.get("os")
    app_version = data.get("app_version")
    client_ip = get_client_ip(request)

    entitlement = db.query_one(
        "SELECT id, org_id, license_key, max_seats, valid_from, valid_until, status FROM license_entitlements WHERE license_key = %s LIMIT 1",
        (license_key,),
    )
    if not entitlement:
        audit(request, "validate_fail", "entitlement", None, {"reason": "license_not_found", "license_key": license_key})
        return {"success": False, "error": "License not found"}

    if entitlement["status"] != "active":
        audit(request, "validate_fail", "entitlement", str(entitlement["id"]), {"reason": "license_inactive", "status": entitlement["status"]})
        return {"success": False, "error": "License is not active"}

    if entitlement["org_id"] != org_id:
        audit(request, "validate_fail", "entitlement", str(entitlement["id"]), {"reason": "org_mismatch"})
        return {"success": False, "error": "Organization does not match license"}

    now = _now()
    now_str = _now_str()
    valid_until = _ensure_utc(entitlement.get("valid_until"))
    valid_from = _ensure_utc(entitlement.get("valid_from"))
    if valid_until and valid_until < now:
        audit(request, "validate_fail", "entitlement", str(entitlement["id"]), {"reason": "license_expired"})
        return {"success": False, "error": "License has expired"}
    if valid_from and valid_from > now:
        audit(request, "validate_fail", "entitlement", str(entitlement["id"]), {"reason": "license_not_yet_valid"})
        return {"success": False, "error": "License is not yet valid"}

    entitlement_id = entitlement["id"]
    active_rows = db.query(
        "SELECT id, device_id, last_heartbeat_at FROM seat_allocations WHERE entitlement_id = %s",
        (entitlement_id,),
    )
    active_allocations = [r for r in active_rows if is_allocation_active(r.get("last_heartbeat_at"))]
    active_count = len(active_allocations)
    existing = next((r for r in active_rows if r["device_id"] == device_id), None)

    if existing and is_allocation_active(existing.get("last_heartbeat_at")):
        db.execute(
            "UPDATE seat_allocations SET last_heartbeat_at = %s, hostname = %s, os = %s, app_version = %s, client_ip = %s, updated_at = %s WHERE id = %s",
            (now, hostname or None, os_name or None, app_version or None, client_ip, now, existing["id"]),
        )
        audit(request, "validate_success", "seat_allocation", str(existing["id"]), {"reattach": True})
        return {"success": True, "allocation": {"seat_id": str(existing["id"]), "reattach": True}}

    if active_count >= entitlement["max_seats"] and not existing:
        audit(
            request,
            "validate_fail",
            "entitlement",
            str(entitlement_id),
            {"reason": "max_seats_exceeded", "active": active_count, "max": entitlement["max_seats"]},
        )
        return {"success": False, "error": "No seats available. Maximum active seats in use."}

    if existing:
        db.execute(
            "UPDATE seat_allocations SET last_heartbeat_at = %s, hostname = %s, os = %s, app_version = %s, client_ip = %s, updated_at = %s WHERE id = %s",
            (now, hostname or None, os_name or None, app_version or None, client_ip, now, existing["id"]),
        )
        audit(request, "validate_success", "seat_allocation", str(existing["id"]), {"reattach": False, "was_stale": True})
        return {"success": True, "allocation": {"seat_id": str(existing["id"]), "reattach": False}}

    lastrowid, _ = db.execute(
        "INSERT INTO seat_allocations (entitlement_id, org_id, device_id, hostname, os, app_version, client_ip, allocated_at, last_heartbeat_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (entitlement_id, org_id, device_id, hostname or None, os_name or None, app_version or None, client_ip, now_str, now_str),
    )
    audit(request, "validate_success", "seat_allocation", str(lastrowid), {"reattach": False})
    return {"success": True, "allocation": {"seat_id": str(lastrowid), "reattach": False}}


def heartbeat(request):
    """Refresh last_heartbeat_at for the allocation for this license + device."""
    data = request.get_json() or {}
    license_key = data.get("license_id")
    org_id = data.get("org_id")
    device_id = data.get("device_id")
    hostname = data.get("hostname")
    os_name = data.get("os")
    app_version = data.get("app_version")
    client_ip = get_client_ip(request)
    now = _now()

    entitlement = db.query_one(
        "SELECT id FROM license_entitlements WHERE license_key = %s AND org_id = %s AND status = %s",
        (license_key, org_id, "active"),
    )
    if not entitlement:
        return {"success": False, "error": "License not found or not active for this organization"}

    alloc = db.query_one(
        "SELECT id, last_heartbeat_at FROM seat_allocations WHERE entitlement_id = %s AND device_id = %s",
        (entitlement["id"], device_id),
    )
    if not alloc:
        return {"success": False, "error": "No seat allocation found for this device. Call validate first."}
    if not is_allocation_active(alloc.get("last_heartbeat_at")):
        return {"success": False, "error": "Seat allocation has expired. Call validate to reallocate."}

    db.execute(
        "UPDATE seat_allocations SET last_heartbeat_at = %s, hostname = %s, os = %s, app_version = %s, client_ip = %s, updated_at = %s WHERE id = %s",
        (now, hostname or None, os_name or None, app_version or None, client_ip, now, alloc["id"]),
    )
    audit(request, "heartbeat", "seat_allocation", str(alloc["id"]), {})
    return {"success": True}


def release(request):
    """Remove seat allocation for this license + device."""
    data = request.get_json() or {}
    license_key = data.get("license_id")
    org_id = data.get("org_id")
    device_id = data.get("device_id")

    entitlement = db.query_one(
        "SELECT id FROM license_entitlements WHERE license_key = %s AND org_id = %s",
        (license_key, org_id),
    )
    if not entitlement:
        return {"success": False, "error": "License not found for this organization"}

    _, rowcount = db.execute(
        "DELETE FROM seat_allocations WHERE entitlement_id = %s AND device_id = %s",
        (entitlement["id"], device_id),
    )
    if rowcount == 0:
        return {"success": False, "error": "No seat allocation found for this device"}
    audit(request, "release", "seat_allocation", None, {"entitlement_id": entitlement["id"], "device_id": device_id})
    return {"success": True}
