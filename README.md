# Licensing Server

Vendor-hosted REST API for **floating, seat-based** licensing of an enterprise desktop application. Clients call over HTTPS with `license_id`, `org_id`, and `device_id`; the server validates entitlements, enforces seat limits, and tracks activity via heartbeats.

**Stack:** Python (Flask), local MySQL 8.x. Default database name: **largon**. All server code lives under **`src/`** (config, db, middleware, routes, services).

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for design overview, decisions, and extension points.

## Prerequisites

- **Python** 3.10+
- **MySQL** 8.x (local; database `largon`)

## Setup

1. **Create virtualenv and install dependencies**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # Linux/macOS
   pip install -r requirements.txt
   ```

2. **Create database and schema (local MySQL)**

   From project root (uses your `.env` credentials):

   ```bash
   python setup_db.py
   ```

   Or manually:

   ```bash
   mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS largon;"
   mysql -u root -p largon < schema.sql
   ```

   Optionally create a dedicated user:

   ```sql
   CREATE USER 'largon'@'localhost' IDENTIFIED BY 'your_password';
   GRANT SELECT, INSERT, UPDATE, DELETE ON largon.* TO 'largon'@'localhost';
   FLUSH PRIVILEGES;
   ```
   Then set `MYSQL_USER=largon` and `MYSQL_PASSWORD=...` in `.env`.

3. **Configure environment**

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # Linux/macOS
   ```
   Edit `.env`: set `MYSQL_PASSWORD` (and `MYSQL_USER` if not root). Default `MYSQL_DATABASE=largon`.

4. **Run the server** (from project root)

   ```bash
   python run.py
   ```

   Or run the module directly: `python src/index.py`.

The server listens on `PORT` (default 3000). In production, run behind a reverse proxy (e.g. nginx) with HTTPS.

## API

Base URL: `http://localhost:3000` (or your host). All request/response bodies are JSON.

### POST /license/validate

Validates the license and allocates or reattaches a seat for the device.

**Request body**

| Field        | Required | Description                          |
|-------------|----------|--------------------------------------|
| license_id  | Yes      | License key (must exist in DB)       |
| org_id      | Yes      | Organization id (must match license) |
| device_id   | Yes      | Stable device identifier             |
| hostname    | No       | Client hostname                      |
| os          | No       | Operating system                     |
| app_version | No       | Application version                  |

**Response (200)** – success

```json
{ "success": true, "allocation": { "seat_id": "1", "reattach": false } }
```

**Response (403)** – validation failed

```json
{ "success": false, "error": "No seats available. Maximum active seats in use." }
```

### POST /license/heartbeat

Refreshes last activity for the current seat allocation. Same body as validate (license_id, org_id, device_id, optional hostname, os, app_version).

**Response (200)** – success  
**Response (403)** – no allocation or allocation expired (client should call validate again).

### POST /license/release

Releases the seat for this device. Same required body: license_id, org_id, device_id.

**Response (200)** – released  
**Response (404)** – no allocation found.

### POST /trial/validate

Validates or starts a trial for the device. Requires `device_id`; optional: org_id, hostname, os, app_version. Behavior depends on `TRIAL_DURATION_SECONDS` (0 = no time limit in this implementation).

**Response (200)** – trial active

```json
{ "success": true, "trial_active": true, "first_use": true, "expires_at": null }
```

**Response (403)** – trial expired.

### GET /health

No body. Returns `{ "status": "ok", "service": "lic-server" }`.

## Example requests

```bash
# Validate license
curl -s -X POST http://localhost:3000/license/validate \
  -H "Content-Type: application/json" \
  -d '{"license_id":"LIC-ACME-001","org_id":"acme-corp","device_id":"my-device-001","hostname":"laptop","os":"Windows 11","app_version":"1.0.0"}'

# Heartbeat
curl -s -X POST http://localhost:3000/license/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"license_id":"LIC-ACME-001","org_id":"acme-corp","device_id":"my-device-001"}'

# Release
curl -s -X POST http://localhost:3000/license/release \
  -H "Content-Type: application/json" \
  -d '{"license_id":"LIC-ACME-001","org_id":"acme-corp","device_id":"my-device-001"}'

# Trial
curl -s -X POST http://localhost:3000/trial/validate \
  -H "Content-Type: application/json" \
  -d '{"device_id":"my-device-001"}'
```

## Client simulator (recommended for testing)

If you want to “act like the desktop app” (validate → periodic heartbeats → release), use:

```bash
python client_sim.py validate --license-id LIC-ACME-001 --org-id acme-corp --device-id dev-1
python client_sim.py session  --license-id LIC-ACME-001 --org-id acme-corp --device-id dev-1 --duration 30 --interval 5 --release
```

Trial:

```bash
python client_sim.py trial --device-id dev-trial-1
```

## Database

- **license_entitlements**: Purchased capacity per org (license_key, max_seats, valid_from, valid_until, status).
- **seat_allocations**: One row per device per license; `last_heartbeat_at` used to consider a seat active or released after TTL.
- **devices**: Device tracking and trial usage (first_seen_at, trial_used_at).
- **audit_log**: Optional action log for compliance/debugging.

See [schema.sql](./schema.sql) for full DDL and example inserts.

## Configuration

| Variable                 | Default | Description                                  |
|--------------------------|--------|----------------------------------------------|
| PORT                     | 3000   | Server port                                  |
| MYSQL_*                  | -      | MySQL connection (host, port, user, password, database) |
| HEARTBEAT_TTL_SECONDS    | 600    | No heartbeat for this long → seat considered released |
| TRIAL_DURATION_SECONDS   | 0      | Trial duration in seconds; 0 = no limit      |

## License

Internal use. No billing or payment integration; no UI; no cryptographic license files or offline licensing in this phase.
