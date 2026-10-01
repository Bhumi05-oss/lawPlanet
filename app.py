"""
LawPlanet Backend
==================
A self-contained Flask + SQLite backend for the LawPlanet demo application.

Run with:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000 in your browser.
"""

import os
import sqlite3
import secrets
import hashlib
import binascii
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request, jsonify, g, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lawplanet.db")

app = Flask(__name__, static_folder=None)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('client', 'lawyer')),
    city TEXT,
    phone TEXT,
    avatar_color TEXT DEFAULT '#0f3d5c',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lawyer_details (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    bar_council_id TEXT,
    practice_area TEXT,
    experience_years INTEGER DEFAULT 0,
    courts TEXT,
    consultation_fee INTEGER DEFAULT 0,
    bio TEXT,
    verified INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lawyer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    practice_area TEXT,
    outcome TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lawyer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, lawyer_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_flag INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
"""


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Password hashing (stdlib only - PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return binascii.hexlify(salt).decode() + ":" + binascii.hexlify(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":")
        salt = binascii.unhexlify(salt_hex)
        expected = binascii.unhexlify(dk_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return secrets.compare_digest(dk, expected)
    except Exception:
        return False


def now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def get_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def current_user():
    token = get_token()
    if not token:
        return None
    db = get_db()
    row = db.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ?""",
        (token,),
    ).fetchone()
    return row


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.current_user["role"] != role:
                return jsonify({"error": f"Only {role}s can perform this action."}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def user_public(row):
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "role": row["role"],
        "city": row["city"],
        "phone": row["phone"],
        "avatar_color": row["avatar_color"],
    }


# ---------------------------------------------------------------------------
# Static frontend serving
# ---------------------------------------------------------------------------

PAGES_DIR = os.path.join(BASE_DIR, "pages")
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.route("/")
def serve_index():
    return send_from_directory(PAGES_DIR, "index.html")


@app.route("/<path:page_name>.html")
def serve_page(page_name):
    return send_from_directory(PAGES_DIR, f"{page_name}.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True, silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role")
    city = (data.get("city") or "").strip()

    if not full_name or not email or not password or role not in ("client", "lawyer"):
        return jsonify({"error": "full_name, email, password and a valid role are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "An account with this email already exists."}), 409

    colors = ["#0f3d5c", "#1c5d78", "#0b6e6e", "#8a6d1f", "#5c3d99", "#2a6f4d"]
    avatar_color = secrets.choice(colors)

    cur = db.execute(
        """INSERT INTO users (full_name, email, password_hash, role, city, phone, avatar_color, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (full_name, email, hash_password(password), role, city, data.get("phone", ""), avatar_color, now()),
    )
    user_id = cur.lastrowid

    if role == "lawyer":
        db.execute(
            """INSERT INTO lawyer_details (user_id, bar_council_id, practice_area, experience_years, courts, consultation_fee, bio)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                data.get("bar_council_id", ""),
                data.get("practice_area", ""),
                int(data.get("experience_years") or 0),
                data.get("courts", ""),
                int(data.get("consultation_fee") or 0),
                data.get("bio", ""),
            ),
        )

    token = secrets.token_hex(24)
    db.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now()))
    db.commit()

    user_row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return jsonify({"token": token, "user": user_public(user_row)}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return jsonify({"error": "Invalid email or password."}), 401

    token = secrets.token_hex(24)
    db.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, row["id"], now()))
    db.commit()
    return jsonify({"token": token, "user": user_public(row)})


@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    db = get_db()
    db.execute("DELETE FROM sessions WHERE token = ?", (get_token(),))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/me", methods=["GET"])
@login_required
def me():
    user = g.current_user
    result = user_public(user)
    if user["role"] == "lawyer":
        db = get_db()
        ld = db.execute("SELECT * FROM lawyer_details WHERE user_id = ?", (user["id"],)).fetchone()
        if ld:
            result["lawyer_details"] = dict(ld)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Profile routes
# ---------------------------------------------------------------------------

@app.route("/api/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json(force=True, silent=True) or {}
    db = get_db()
    db.execute(
        "UPDATE users SET full_name = ?, city = ?, phone = ? WHERE id = ?",
        (
            data.get("full_name", g.current_user["full_name"]),
            data.get("city", g.current_user["city"]),
            data.get("phone", g.current_user["phone"]),
            g.current_user["id"],
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (g.current_user["id"],)).fetchone()
    return jsonify(user_public(row))


@app.route("/api/lawyer-details", methods=["PUT"])
@login_required
@role_required("lawyer")
def update_lawyer_details():
    data = request.get_json(force=True, silent=True) or {}
    db = get_db()
    db.execute(
        """UPDATE lawyer_details SET bar_council_id=?, practice_area=?, experience_years=?,
           courts=?, consultation_fee=?, bio=? WHERE user_id=?""",
        (
            data.get("bar_council_id", ""),
            data.get("practice_area", ""),
            int(data.get("experience_years") or 0),
            data.get("courts", ""),
            int(data.get("consultation_fee") or 0),
            data.get("bio", ""),
            g.current_user["id"],
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM lawyer_details WHERE user_id = ?", (g.current_user["id"],)).fetchone()
    return jsonify(dict(row))


# ---------------------------------------------------------------------------
# Lawyer directory
# ---------------------------------------------------------------------------

@app.route("/api/lawyers", methods=["GET"])
def list_lawyers():
    city = request.args.get("city", "").strip()
    practice_area = request.args.get("practice_area", "").strip()
    min_experience = request.args.get("min_experience", "").strip()
    q = request.args.get("q", "").strip()

    sql = """
        SELECT u.id, u.full_name, u.city, u.avatar_color,
               ld.practice_area, ld.experience_years, ld.consultation_fee,
               ld.courts, ld.bio, ld.bar_council_id, ld.verified
        FROM users u JOIN lawyer_details ld ON ld.user_id = u.id
        WHERE u.role = 'lawyer'
    """
    params = []
    if city:
        sql += " AND u.city LIKE ?"
        params.append(f"%{city}%")
    if practice_area:
        sql += " AND ld.practice_area LIKE ?"
        params.append(f"%{practice_area}%")
    if min_experience.isdigit():
        sql += " AND ld.experience_years >= ?"
        params.append(int(min_experience))
    if q:
        sql += " AND u.full_name LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY ld.experience_years DESC"

    db = get_db()
    rows = db.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/lawyers/<int:lawyer_id>", methods=["GET"])
def get_lawyer(lawyer_id):
    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE id = ? AND role = 'lawyer'", (lawyer_id,)).fetchone()
    if not user_row:
        return jsonify({"error": "Lawyer not found."}), 404
    ld = db.execute("SELECT * FROM lawyer_details WHERE user_id = ?", (lawyer_id,)).fetchone()
    cases = db.execute(
        "SELECT * FROM cases WHERE lawyer_id = ? ORDER BY created_at DESC", (lawyer_id,)
    ).fetchall()
    result = user_public(user_row)
    result["lawyer_details"] = dict(ld) if ld else {}
    result["cases"] = [dict(c) for c in cases]
    return jsonify(result)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

@app.route("/api/cases", methods=["POST"])
@login_required
@role_required("lawyer")
def create_case():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Case title is required."}), 400
    db = get_db()
    cur = db.execute(
        """INSERT INTO cases (lawyer_id, title, description, practice_area, outcome, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'open', ?)""",
        (
            g.current_user["id"],
            title,
            data.get("description", ""),
            data.get("practice_area", ""),
            data.get("outcome", ""),
            now(),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM cases WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/cases/mine", methods=["GET"])
@login_required
@role_required("lawyer")
def my_cases():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM cases WHERE lawyer_id = ? ORDER BY created_at DESC", (g.current_user["id"],)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/cases/<int:case_id>", methods=["PUT"])
@login_required
@role_required("lawyer")
def update_case(case_id):
    db = get_db()
    row = db.execute("SELECT * FROM cases WHERE id = ? AND lawyer_id = ?", (case_id, g.current_user["id"])).fetchone()
    if not row:
        return jsonify({"error": "Case not found."}), 404
    data = request.get_json(force=True, silent=True) or {}
    db.execute(
        """UPDATE cases SET title=?, description=?, practice_area=?, outcome=?, status=? WHERE id=?""",
        (
            data.get("title", row["title"]),
            data.get("description", row["description"]),
            data.get("practice_area", row["practice_area"]),
            data.get("outcome", row["outcome"]),
            data.get("status", row["status"]),
            case_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/cases/<int:case_id>", methods=["DELETE"])
@login_required
@role_required("lawyer")
def delete_case(case_id):
    db = get_db()
    row = db.execute("SELECT * FROM cases WHERE id = ? AND lawyer_id = ?", (case_id, g.current_user["id"])).fetchone()
    if not row:
        return jsonify({"error": "Case not found."}), 404
    db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Conversations & messages
# ---------------------------------------------------------------------------

def conversation_partner_info(db, conv_row, my_id):
    partner_id = conv_row["lawyer_id"] if conv_row["client_id"] == my_id else conv_row["client_id"]
    partner = db.execute("SELECT * FROM users WHERE id = ?", (partner_id,)).fetchone()
    last_msg = db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1",
        (conv_row["id"],),
    ).fetchone()
    unread = db.execute(
        "SELECT COUNT(*) as c FROM messages WHERE conversation_id = ? AND sender_id != ? AND read_flag = 0",
        (conv_row["id"], my_id),
    ).fetchone()["c"]
    return {
        "id": conv_row["id"],
        "partner": user_public(partner) if partner else None,
        "last_message": last_msg["content"] if last_msg else None,
        "last_message_at": last_msg["created_at"] if last_msg else conv_row["created_at"],
        "unread_count": unread,
    }


@app.route("/api/conversations", methods=["GET"])
@login_required
def list_conversations():
    db = get_db()
    uid = g.current_user["id"]
    rows = db.execute(
        "SELECT * FROM conversations WHERE client_id = ? OR lawyer_id = ? ORDER BY created_at DESC",
        (uid, uid),
    ).fetchall()
    result = [conversation_partner_info(db, r, uid) for r in rows]
    result.sort(key=lambda c: c["last_message_at"] or "", reverse=True)
    return jsonify(result)


@app.route("/api/conversations", methods=["POST"])
@login_required
@role_required("client")
def start_conversation():
    data = request.get_json(force=True, silent=True) or {}
    lawyer_id = data.get("lawyer_id")
    db = get_db()
    lawyer = db.execute("SELECT * FROM users WHERE id = ? AND role = 'lawyer'", (lawyer_id,)).fetchone()
    if not lawyer:
        return jsonify({"error": "Lawyer not found."}), 404

    existing = db.execute(
        "SELECT * FROM conversations WHERE client_id = ? AND lawyer_id = ?",
        (g.current_user["id"], lawyer_id),
    ).fetchone()
    if existing:
        conv_id = existing["id"]
    else:
        cur = db.execute(
            "INSERT INTO conversations (client_id, lawyer_id, created_at) VALUES (?, ?, ?)",
            (g.current_user["id"], lawyer_id, now()),
        )
        db.commit()
        conv_id = cur.lastrowid

    conv_row = db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    return jsonify(conversation_partner_info(db, conv_row, g.current_user["id"])), 201


@app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
@login_required
def get_messages(conv_id):
    db = get_db()
    uid = g.current_user["id"]
    conv = db.execute(
        "SELECT * FROM conversations WHERE id = ? AND (client_id = ? OR lawyer_id = ?)",
        (conv_id, uid, uid),
    ).fetchone()
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404

    db.execute(
        "UPDATE messages SET read_flag = 1 WHERE conversation_id = ? AND sender_id != ?",
        (conv_id, uid),
    )
    db.commit()

    rows = db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conv_id,)
    ).fetchall()
    partner_info = conversation_partner_info(db, conv, uid)
    return jsonify({"partner": partner_info["partner"], "messages": [dict(r) for r in rows]})


@app.route("/api/conversations/<int:conv_id>/messages", methods=["POST"])
@login_required
def send_message(conv_id):
    data = request.get_json(force=True, silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Message content cannot be empty."}), 400

    db = get_db()
    uid = g.current_user["id"]
    conv = db.execute(
        "SELECT * FROM conversations WHERE id = ? AND (client_id = ? OR lawyer_id = ?)",
        (conv_id, uid, uid),
    ).fetchone()
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404

    cur = db.execute(
        "INSERT INTO messages (conversation_id, sender_id, content, created_at) VALUES (?, ?, ?, ?)",
        (conv_id, uid, content, now()),
    )
    db.commit()
    row = db.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

@app.route("/api/meta", methods=["GET"])
def meta():
    return jsonify({
        "cities": ["Delhi", "Mumbai", "Bengaluru", "Kolkata", "Chennai", "Hyderabad",
                   "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Chandigarh"],
        "practice_areas": ["Civil", "Criminal", "Family", "Property", "Corporate",
                            "Tax", "Labour", "Constitutional", "IPR", "Consumer"],
    })


if __name__ == "__main__":
    init_db()
    print("LawPlanet running at http://localhost:5000")
    app.run(debug=True, port=5000)
