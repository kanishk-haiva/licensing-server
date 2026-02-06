"""
Configuration from environment. No hardcoded secrets or business rules.
Copy .env.example to .env at project root. Default DB is local MySQL database 'largon'.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of src)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PORT = int(os.environ.get("PORT", "3000"))
NODE_ENV = os.environ.get("NODE_ENV", "development")

# Local MySQL — default database name 'largon'
MYSQL = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "largon"),
}

# Seat considered released if no heartbeat for this many seconds
HEARTBEAT_TTL_SECONDS = int(os.environ.get("HEARTBEAT_TTL_SECONDS", "600"))

# Trial: max duration in seconds; 0 = disabled or no time limit
TRIAL_DURATION_SECONDS = int(os.environ.get("TRIAL_DURATION_SECONDS", "0"))
