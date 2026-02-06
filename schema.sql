-- Licensing Server Schema (MySQL 8.x)
-- Use with local MySQL; default database name: largon.
-- Vendor-neutral, surrogate keys + indexed business keys for lookups.

-- ---------------------------------------------------------------------------
-- License entitlements: purchased license capacity per organization
-- license_key: value sent by client as license_id; must be unique
-- ---------------------------------------------------------------------------
CREATE TABLE license_entitlements (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  org_id        VARCHAR(128)    NOT NULL COMMENT 'Organization identifier from client',
  license_key   VARCHAR(256)    NOT NULL COMMENT 'License identifier sent by client (license_id)',
  max_seats     INT UNSIGNED   NOT NULL DEFAULT 1,
  valid_from    DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  valid_until   DATETIME(3)    NULL     COMMENT 'NULL = no expiry',
  status        VARCHAR(32)    NOT NULL DEFAULT 'active' COMMENT 'e.g. active, suspended, revoked',
  created_at    DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at    DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_license_key (license_key),
  KEY ix_org_id (org_id),
  KEY ix_status_valid_until (status, valid_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Active seat allocations: one row per device per license (floating seats)
-- Same device cannot hold more than one seat for the same license
-- ---------------------------------------------------------------------------
CREATE TABLE seat_allocations (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  entitlement_id      BIGINT UNSIGNED NOT NULL,
  org_id              VARCHAR(128)    NOT NULL,
  device_id           VARCHAR(256)    NOT NULL,
  hostname            VARCHAR(256)    NULL,
  os                  VARCHAR(128)    NULL,
  app_version         VARCHAR(64)     NULL,
  client_ip           VARCHAR(45)     NULL,
  allocated_at        DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  last_heartbeat_at   DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_entitlement_device (entitlement_id, device_id),
  KEY ix_entitlement_id (entitlement_id),
  KEY ix_org_id (org_id),
  KEY ix_last_heartbeat (last_heartbeat_at),
  CONSTRAINT fk_seat_entitlement FOREIGN KEY (entitlement_id) REFERENCES license_entitlements (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Device registration / tracking: first/last seen, trial usage, analytics
-- ---------------------------------------------------------------------------
CREATE TABLE devices (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  device_id      VARCHAR(256)    NOT NULL COMMENT 'Stable device identifier from client',
  org_id         VARCHAR(128)    NULL     COMMENT 'NULL for trial-only devices',
  first_seen_at  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  last_seen_at   DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  trial_used_at  DATETIME(3)     NULL     COMMENT 'When trial was first used (if any)',
  metadata       JSON            NULL     COMMENT 'Optional hostname, os, app_version snapshot',
  created_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_device_id (device_id),
  KEY ix_org_id (org_id),
  KEY ix_last_seen (last_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Optional audit log: actions for compliance and debugging
-- ---------------------------------------------------------------------------
CREATE TABLE audit_log (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  action      VARCHAR(64)    NOT NULL COMMENT 'e.g. validate_success, heartbeat, release, trial_start',
  entity_type VARCHAR(64)    NULL     COMMENT 'e.g. seat_allocation, device, entitlement',
  entity_id   VARCHAR(128)   NULL,
  payload     JSON           NULL     COMMENT 'Request/response snapshot or ids',
  client_ip   VARCHAR(45)    NULL,
  created_at  DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY ix_action_created (action, created_at),
  KEY ix_entity (entity_type, entity_id),
  KEY ix_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Example data (for development / review)
-- ---------------------------------------------------------------------------

-- One entitlement: org "acme-corp" has 3 seats for license key "LIC-ACME-001", valid until end of 2026
INSERT INTO license_entitlements (org_id, license_key, max_seats, valid_from, valid_until, status)
VALUES ('acme-corp', 'LIC-ACME-001', 3, '2025-01-01 00:00:00.000', '2026-12-31 23:59:59.999', 'active');

-- Another org with 1 seat
INSERT INTO license_entitlements (org_id, license_key, max_seats, valid_from, valid_until, status)
VALUES ('globex-inc', 'LIC-GLOBEX-001', 1, '2025-01-01 00:00:00.000', NULL, 'active');

-- Two active seat allocations for LIC-ACME-001 (entitlement id 1)
INSERT INTO seat_allocations (entitlement_id, org_id, device_id, hostname, os, app_version, client_ip)
VALUES
  (1, 'acme-corp', 'device-alfa-001', 'laptop-john', 'Windows 11', '1.2.0', '203.0.113.10'),
  (1, 'acme-corp', 'device-beta-002', 'laptop-jane', 'macOS 14', '1.2.0', '203.0.113.11');

-- One device record (trial not yet used)
INSERT INTO devices (device_id, org_id, first_seen_at, last_seen_at, metadata)
VALUES ('device-alfa-001', 'acme-corp', NOW(3), NOW(3), '{"hostname":"laptop-john","os":"Windows 11"}');

-- Sample audit entry
INSERT INTO audit_log (action, entity_type, entity_id, payload, client_ip)
VALUES ('validate_success', 'seat_allocation', '1', '{"license_key":"LIC-ACME-001","device_id":"device-alfa-001"}', '203.0.113.10');
