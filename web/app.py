"""
KitchenOS Web UI — Flask server.
Serves the landing page and proxies chat messages to the ADK backend (port 8000).
"""

import os
import json
import requests
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    stream_with_context,
)
import litellm

app = Flask(__name__)

ADK_BASE = os.getenv("ADK_BASE_URL", "http://localhost:8000")
APP_NAME = "head_chef"
DEFAULT_USER = "user"


def _pg_conn():
    """Return a fresh Postgres connection."""
    import psycopg2

    conn_str = os.getenv(
        "POSTGRES_CONNECTION_STRING",
        "postgresql://user:password@localhost:5432/mychef_db",
    )
    return psycopg2.connect(conn_str)


@app.route("/")
def index():
    """Landing page."""
    return render_template("index.html")


@app.route("/chat")
def chat_page():
    """Chat interface page."""
    return render_template("chat.html")


@app.route("/api/session", methods=["POST"])
def create_session():
    """Create a new ADK session."""
    try:
        resp = requests.post(
            f"{ADK_BASE}/apps/{APP_NAME}/users/{DEFAULT_USER}/sessions",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return jsonify({"session_id": data.get("id") or data.get("session_id")})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/chat", methods=["POST"])
def chat():
    """Proxy a chat message to the ADK backend and stream the SSE response."""
    body = request.json
    session_id = body.get("session_id")
    message = body.get("message", "")

    if not session_id or not message:
        return jsonify({"error": "session_id and message are required"}), 400

    payload = {
        "app_name": APP_NAME,
        "user_id": DEFAULT_USER,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [{"text": message}],
        },
        "streaming": False,
    }

    def generate():
        try:
            resp = requests.post(
                f"{ADK_BASE}/run_sse",
                json=payload,
                stream=True,
                timeout=120,
            )
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    yield decoded + "\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
    )


@app.route("/api/pantry")
def get_pantry():
    """Fetch pantry items from Postgres."""
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT item_name, quantity, unit, purchase_date, expiry_date FROM pantry ORDER BY expiry_date ASC"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        items = [
            {
                "name": r[0],
                "quantity": r[1],
                "unit": r[2],
                "purchased": r[3].isoformat() if r[3] else None,
                "expiry": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/family")
def get_family():
    """Fetch family members and their dietary profiles."""
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT fm.id, fm.name, fm.relationship, dp.trait_type, dp.value
               FROM family_members fm
               LEFT JOIN dietary_profiles dp ON fm.id = dp.member_id
               ORDER BY fm.id"""
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        members = {}
        for mid, name, rel, trait, val in rows:
            if mid not in members:
                members[mid] = {
                    "id": mid,
                    "name": name,
                    "relationship": rel,
                    "traits": [],
                }
            if trait and val:
                members[mid]["traits"].append({"type": trait, "value": val})

        return jsonify(list(members.values()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/schema")
def get_schema():
    """Fetch the DB schema (table names and columns) for display."""
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        tables = {}
        for tbl, col, dtype, nullable in rows:
            if tbl not in tables:
                tables[tbl] = []
            tables[tbl].append(
                {
                    "column": col,
                    "type": dtype,
                    "nullable": nullable == "YES",
                }
            )

        return jsonify(tables)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profile/parse", methods=["POST"])
def parse_profile():
    """Use LiteLLM to extract structured family profiles from natural text."""
    body = request.json
    text = body.get("text", "")

    prompt = f"""
    You are an exact JSON extractor. Extract family members, their relationships, diets, and allergies from the text.
    Return ONLY valid JSON matching this schema:
    {{"members": [{{"name": "str", "relationship": "self|spouse|child|etc", "diets": ["str"], "allergies": ["str"]}}]}}
    
    Text: {text}
    """

    try:
        response = litellm.completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return jsonify(json.loads(content))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profile/save", methods=["POST"])
def save_profile():
    """Save the extracted profile JSON to the PostgreSQL database."""
    body = request.json
    members = body.get("members", [])

    try:
        conn = _pg_conn()
        cur = conn.cursor()

        for m in members:
            # Upsert family member (simplified insert, in reality might check for existence)
            cur.execute(
                "INSERT INTO family_members (name, relationship) VALUES (%s, %s) RETURNING id",
                (m.get("name"), m.get("relationship", "member")),
            )
            member_id = cur.fetchone()[0]

            # Insert diets
            for diet in m.get("diets", []):
                cur.execute(
                    "INSERT INTO dietary_profiles (member_id, trait_type, value) VALUES (%s, 'diet', %s)",
                    (member_id, diet),
                )

            # Insert allergies
            for allergy in m.get("allergies", []):
                cur.execute(
                    "INSERT INTO dietary_profiles (member_id, trait_type, value) VALUES (%s, 'allergy', %s)",
                    (member_id, allergy),
                )

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pantry/parse_and_save", methods=["POST"])
def parse_and_save_pantry():
    """Use LiteLLM to extract pantry items from natural text and save to DB."""
    body = request.json
    text = body.get("text", "")

    prompt = f"""
    You are an exact JSON extractor. Extract pantry inventory from the text.
    Return ONLY valid JSON matching this schema:
    {{"items": [{{"item_name": "str", "quantity": float, "unit": "str"}}]}}
    Default unit to 'unit' if not specified.
    
    Text: {text}
    """

    try:
        # LLM Parse
        response = litellm.completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        items = data.get("items", [])

        # Save to DB
        conn = _pg_conn()
        cur = conn.cursor()
        for i in items:
            cur.execute(
                "INSERT INTO pantry (item_name, quantity, unit) VALUES (%s, %s, %s)",
                (i.get("item_name"), i.get("quantity", 1), i.get("unit", "unit")),
            )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "parsed_items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
