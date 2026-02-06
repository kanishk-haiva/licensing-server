# Licensing Server — Architecture Overview

## Summary

Vendor-hosted REST API that enforces **floating, seat-based** licenses for a desktop application. Clients call over HTTPS with `license_id`, `org_id`, and `device_id`; the server validates entitlements, enforces seat limits, and tracks activity via heartbeats.

---

## High-Level Flow

```
┌─────────────────┐         HTTPS          ┌─────────────────────┐
│ Desktop Client  │ ◄─────────────────────► │ Licensing Server    │
│ (binary app)    │   validate / heartbeat │ (python + flask)   │
└─────────────────┘         / release     └──────────┬──────────┘
                                                      │
                                                      ▼
                                            ┌─────────────────────┐
                                            │ MySQL 8.x           │
                                            │ (entitlements,      │
                                            │  seats, devices)    │
                                            └─────────────────────┘
```

- **Validate**: Check license exists, is active, not expired; ensure org matches; allocate or reattach a seat for the device (within seat limit).
- **Heartbeat**: Update `last_heartbeat_at` for the current seat allocation so the seat is considered “in use.”
- **Release**: Explicitly free the seat for that device (optional; heartbeats can also time out).
- **Trial validate**: Separate path for time- or use-limited trials keyed by `device_id` (optional).

---

## Design Decisions

### 1. Server-side enforcement only

- All checks (validity, expiry, seat count) happen on the server. The client only sends identifiers and receives allow/deny. No crypto license files or offline logic in scope.

### 2. Seat allocation model

- **Floating seats**: No permanent assignment of a seat to a device; any device from the org can use one of the N seats while it has a valid allocation.
- **Allocation = row in `seat_allocations`** for a given license and device. One device can hold at most one seat per license (enforced by unique constraint).
- **Reclamation**: If heartbeats stop, the server can treat the seat as abandoned after a configurable TTL (e.g. 10 minutes). This is implemented by comparing `last_heartbeat_at` to current time during validate/heartbeat rather than a background job, to keep the design simple.

### 3. Device identification

- Client sends a stable `device_id` (assumed hardware-based, opaque to the server). Used for:
  - Ensuring one seat per device per license (no duplicate allocation).
  - Trial tracking (one trial per device, or per device+org, as configured).
  - Future abuse or analytics (stored in `devices` and optionally in audit logs).

### 4. No authentication in this phase

- No API keys or OAuth. Validation is “does this (license_id, org_id, device_id) match an active entitlement and seat rules?”. Authentication (e.g. API key, mTLS) can be added later as middleware.

### 5. Database and schema

- **MySQL 8.x** with surrogate keys (`id`) and indexed business keys (`license_key`, `org_id`, `device_id`) for stable lookups and joins.
- **Generic, vendor-neutral** names (e.g. `license_entitlements`, `seat_allocations`, `devices`) so the same schema can support multiple products or SKUs later (e.g. via `product_id` or similar).

### 6. Heartbeat TTL

- A seat is considered “active” only if `last_heartbeat_at` is within the configured TTL (e.g. 10 minutes). Allocations older than that are ignored when counting active seats and can be overwritten by a new validate. Optional cleanup job could delete stale rows; for phase 1 we only treat them as logically released.

### 7. Idempotency and reattach

- If the same device calls validate again while it already has an allocation with a recent heartbeat, the server returns success and optionally refreshes heartbeat (reattach). No duplicate seat is created.

### 8. Optional audit log

- A generic `audit_log` table stores action, entity type, entity id, and optional JSON payload. Useful for compliance and debugging; can be extended later (e.g. retention, sampling).

---

## API Contract (Summary)

| Endpoint                 | Purpose |
|--------------------------|--------|
| `POST /license/validate` | Check license and allocate/reattach a seat for the device. |
| `POST /license/heartbeat` | Refresh last activity for the current allocation. |
| `POST /license/release`   | Release the seat for this device (optional). |
| `POST /trial/validate`    | Validate or start a trial for the device (optional). |

Request body (common fields): `license_id`, `org_id`, `device_id`, `hostname`, `os`, `app_version`; IP can be taken from `X-Forwarded-For` or `req.ip` when behind a proxy.

---

## Extension Points

- **Auth**: Add middleware to verify API key or client certificate before route handlers.
- **Products/SKUs**: Add `product_id` to `license_entitlements` and scope checks by product.
- **Offline / local server**: Out of scope for this phase; would require signed tokens or a separate local service.
- **Billing**: Separate service consuming audit or allocation events; no billing in this server.
- **Stale allocation cleanup**: Cron or scheduled job to `DELETE` from `seat_allocations` where `last_heartbeat_at` is older than TTL.
