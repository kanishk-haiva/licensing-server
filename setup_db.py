"""
Create the MySQL database (e.g. largon) and load schema. Run once before first start.
Uses the same MYSQL_* settings as the app (.env). Run from project root: python setup_db.py
"""
import sys
from pathlib import Path

# Load config from src
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import config
import pymysql

def main():
    db_name = config.MYSQL["database"]
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}")
        sys.exit(1)

    # Connect without database to create it
    conn = pymysql.connect(
        host=config.MYSQL["host"],
        port=config.MYSQL["port"],
        user=config.MYSQL["user"],
        password=config.MYSQL["password"],
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        conn.select_db(db_name)
        sql = schema_path.read_text(encoding="utf-8")
        # Drop full-line comments so semicolons in "-- text; more" don't split incorrectly
        lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
        sql_clean = "\n".join(lines)
        statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()
        print(f"Database '{db_name}' created and schema loaded from schema.sql")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
