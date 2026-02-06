"""
MySQL connection helper. Uses PyMySQL; one connection per request (no pool) for simplicity.
In production you can switch to a connection pool (e.g. DBUtils).
"""
import pymysql
from pymysql.cursors import DictCursor

import config

def get_connection():
    """Return a new connection (caller must close or use context manager)."""
    return pymysql.connect(
        host=config.MYSQL["host"],
        port=config.MYSQL["port"],
        user=config.MYSQL["user"],
        password=config.MYSQL["password"],
        database=config.MYSQL["database"],
        cursorclass=DictCursor,
        autocommit=True,
    )


def query(sql, args=None):
    """Execute SELECT and return list of dicts (rows)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()
    finally:
        conn.close()


def query_one(sql, args=None):
    """Execute SELECT and return first row (dict) or None."""
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=None):
    """Execute INSERT/UPDATE/DELETE; returns (lastrowid, rowcount)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.lastrowid, cur.rowcount
    finally:
        conn.close()
