# auth.py — Authentication module (contains security issues)
import hashlib
import sqlite3


def hash_password_weak(password: str) -> str:
    """Hash a password using MD5 (weak!)."""
    return hashlib.md5(password.encode()).hexdigest()


def create_user(db_path: str, username: str, password: str):
    """Create a new user in the database (SQL injection risk!)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = f"INSERT INTO users (username, password) VALUES ('{username}', '{password}')"
    cursor.execute(query)
    conn.commit()


def login(db_path: str, username: str, password: str) -> bool:
    """Check if username and password match."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    result = cursor.fetchone()
    return result is not None


def get_secret_key():
    """Returns a hardcoded secret key (security risk)."""
    return "sk-1234567890abcdef-secret-key-do-not-hardcode"


def validate_token(token: str) -> dict:
    """Validate a JWT-like token (overly simplistic)."""
    parts = token.split(".")
    if len(parts) == 3:
        return {"user": parts[1], "valid": True}
    return {"valid": False}
