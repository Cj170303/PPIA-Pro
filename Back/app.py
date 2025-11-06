# app.py
# -*- coding: utf-8 -*-
import os
import csv
import re
import json
import sqlite3
import io
from datetime import datetime
from html import escape

from flask import Flask, request, jsonify, session, send_from_directory, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from preguntas_loader import Preguntas

# -----------------------------------
# Config
# -----------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quiz.db")
LOG_CSV = os.path.join(BASE_DIR, "records.csv")
FRONT_DIR = os.path.join(os.path.dirname(BASE_DIR), "Front")
IMAGES_DIR = os.path.join(BASE_DIR, "imagenes")  # <— para logos/salida.png

app = Flask(__name__, static_folder=FRONT_DIR, static_url_path="/")
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key_change_me")
CORS(app, supports_credentials=True)

# CSV header si no existe
if not os.path.isfile(LOG_CSV):
    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "user_id", "question_id", "success"])

USERS_CSV = os.path.join(BASE_DIR, "users.csv")
INTERACTIONS_CSV = os.path.join(BASE_DIR, "interactions.csv")

if not os.path.isfile(USERS_CSV):
    with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["id","full_name","email","uniandes_code","magistral","complementarios","created_at"])

if not os.path.isfile(INTERACTIONS_CSV):
    with open(INTERACTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp","user_id","email","question_id","success"])

# -----------------------------------
# Utilidades de DB
# -----------------------------------
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def require_login():
    return "user_id" in session

# -----------------------------------
# Lógica de selección
# -----------------------------------
def get_available_temas(week: int):
    temas = set()
    for qid, data in Preguntas.items():
        if data["week"] <= week:
            for t in data["tema"].split(","):
                temas.add(t.strip())
    return sorted(t for t in temas if t)

def retrieve_difs_for_temas(temas, week: int):
    difs = set()
    temas_set = set([t.strip() for t in temas])
    for qid, data in Preguntas.items():
        if data["week"] <= week:
            q_temas = set([t.strip() for t in data["tema"].split(",")])
            if q_temas & temas_set:
                difs.add(data["dif"])
    return sorted(difs)

def pick_next_question(user_week, selected_theme, selected_difficulty, answered_ok_ids):
    """
    Selecciona la siguiente pregunta con estas reglas:
      - tema ∩ selected_theme != ∅
      - week <= user_week
      - dif <= selected_difficulty
      - NO repetir las que ya fueron contestadas correctamente en esta sesión
      - PRIORIDAD: preguntas nunca vistas históricamente por este usuario
        (se consulta la tabla SQLite 'interactions')
      - Si no hay no-vistas, se elige entre las candidatas restantes
      - Selección aleatoria entre el conjunto final
    """
    import random

    # 1) Filtros base por tema, semana y dificultad
    temas = set([t.strip() for t in (selected_theme or "").split(",") if t.strip()])
    candidates = []
    for qid, data in Preguntas.items():
        q_temas = set([t.strip() for t in data["tema"].split(",")])
        if q_temas & temas and data["week"] <= user_week and data["dif"] <= selected_difficulty:
            if qid not in (answered_ok_ids or []):  # no repetir acertadas en esta sesión
                candidates.append(qid)

    if not candidates:
        return None

    # 2) Priorizar preguntas "no vistas" históricamente por el usuario (en SQLite)
    seen_by_user = set()
    try:
        # Requiere sesión activa
        uid = session.get("user_id", None)
        if uid is not None:
            con = get_db()
            rows = con.execute(
                "SELECT DISTINCT question_id FROM interactions WHERE user_id = ?",
                (uid,)
            ).fetchall()
            con.close()
            seen_by_user = {int(r["question_id"]) for r in rows}
    except Exception:
        # Si algo falla, no bloqueamos el flujo (simplemente no priorizamos)
        seen_by_user = set()

    unseen = [qid for qid in candidates if qid not in seen_by_user]
    pool = unseen if unseen else candidates

    return random.choice(pool)


def validate_answer(user_response: str, qid: int):
    """
    Extrae la letra (a/B/...) del inicio. Ej: "a", "(A)", "a)". Compara con res.
    """
    m = re.match(r'^\(?\s*([A-Za-z])\)?', user_response.strip())
    if not m:
        return False
    letra = m.group(1).lower()
    correctas = [r.lower() for r in Preguntas[qid]["res"]]
    return letra in correctas

# -----------------------------------
# Endpoints de autenticación
# -----------------------------------
@app.post("/api/register")
def register():
    data = request.get_json() or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    uniandes_code = (data.get("uniandes_code") or "").strip()
    magistral = (data.get("magistral") or "").strip()
    complementarios = (data.get("complementarios") or "").strip()
    password = (data.get("password") or "").strip()

    if not (full_name and email and uniandes_code and magistral and complementarios and password):
        return jsonify({"error": "Faltan campos obligatorios"}), 400
    if not email.endswith("@uniandes.edu.co"):
        return jsonify({"error": "El correo debe ser @uniandes.edu.co"}), 400

    pwd_hash = generate_password_hash(password)
    con = get_db()
    try:
        con.execute("""
            INSERT INTO users (full_name, email, uniandes_code, magistral, complementarios, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (full_name, email, uniandes_code, magistral, complementarios, pwd_hash, datetime.utcnow().isoformat()))
        con.commit()

        new_user_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = con.execute("""
            SELECT id, full_name, email, uniandes_code, magistral, complementarios, created_at
            FROM users WHERE id = ?
        """, (new_user_id,)).fetchone()

        with open(USERS_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                row["id"], row["full_name"], row["email"], row["uniandes_code"],
                row["magistral"], row["complementarios"], row["created_at"]
            ])
    except sqlite3.IntegrityError:
        return jsonify({"error": "Ya existe un usuario con ese correo"}), 409
    finally:
        con.close()

    return jsonify({"ok": True})


@app.post("/api/login")
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    con = get_db()
    row = con.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    con.close()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    session["user_id"] = int(row["id"])
    # Estado de sesión para el flujo del quiz
    session["user_week"] = None
    session["selected_theme"] = None
    session["selected_difficulty"] = None
    session["answered_ok_ids"] = []  # evitar repetir correctas
    session["current_qid"] = None

    return jsonify({"ok": True})

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.get("/api/me")
def me():
    if not require_login():
        return jsonify({"logged": False})
    return jsonify({"logged": True, "user_id": session["user_id"]})

# -----------------------------------
# Flujo: semana → temas/dificultad → quiz
# -----------------------------------
@app.post("/api/set_week")
def set_week():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    data = request.get_json() or {}
    try:
        week = int(data.get("week"))
    except:
        return jsonify({"error": "Semana inválida"}), 400

    # Normalizamos y acotamos: 1 <= semana <= 16
    if week < 1:
        week = 1
    if week > 16:
        week = 16

    session["user_week"] = week
    return jsonify({"ok": True, "week": week})
@app.get("/api/themes_difs")
def themes_difs():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    week = session.get("user_week")
    if week is None:
        return jsonify({"error": "Primero seleccione la semana"}), 400
    temas = get_available_temas(week)
    difs = retrieve_difs_for_temas(temas, week)
    return jsonify({"temas": temas, "difs": difs})

@app.post("/api/start_quiz")
def start_quiz():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    data = request.get_json() or {}
    theme = (data.get("theme") or "").strip()  # puede venir "logica, conjuntos"
    try:
        difficulty = int(data.get("difficulty"))
    except:
        return jsonify({"error": "Dificultad inválida"}), 400

    if session.get("user_week") is None:
        return jsonify({"error": "Primero seleccione la semana"}), 400

    # Guardar selección
    session["selected_theme"] = theme
    session["selected_difficulty"] = difficulty
    session["answered_ok_ids"] = []
    session["current_qid"] = None

    # Preparar primera pregunta
    qid = pick_next_question(session["user_week"], theme, difficulty, session["answered_ok_ids"])
    if qid is None:
        return jsonify({"error": "No hay preguntas para los parámetros seleccionados"}), 404

    session["current_qid"] = qid
    q = Preguntas[qid]
    return jsonify({
        "question_id": qid,
        "html": q["enunciado_html"],
        "tema": q["tema"],
        "dif": q["dif"],
        "week": q["week"]
    })

@app.get("/api/question")
def get_question():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    qid = session.get("current_qid")
    if not qid:
        return jsonify({"error": "No hay pregunta activa"}), 400
    q = Preguntas[qid]
    return jsonify({
        "question_id": qid,
        "html": q["enunciado_html"],
        "tema": q["tema"],
        "dif": q["dif"],
        "week": q["week"]
    })

@app.post("/api/answer")
def answer():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401

    data = request.get_json() or {}
    user_resp = (data.get("answer") or "").strip()

    qid = session.get("current_qid")
    if not qid:
        return jsonify({"error": "No hay pregunta activa"}), 400

    # 1) Validar respuesta
    ok = validate_answer(user_resp, qid)

    # 2) Persistir interacción en SQLite
    con = get_db()
    try:
        con.execute("""
            INSERT INTO interactions (user_id, question_id, success, ts)
            VALUES (?, ?, ?, ?)
        """, (session["user_id"], qid, 1 if ok else 0, datetime.utcnow().isoformat()))
        con.commit()

        u = con.execute("SELECT email FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        email = u["email"] if u else ""
    finally:
        con.close()

    # 3) Log en CSV (opcional para auditoría)
    with open(INTERACTIONS_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(),
            session["user_id"],
            email,
            qid,
            1 if ok else 0
        ])

    # 4) Evitar repetir en esta sesión las preguntas acertadas
    if ok:
        answered_ok = set(session.get("answered_ok_ids") or [])
        answered_ok.add(qid)
        session["answered_ok_ids"] = list(answered_ok)

    # 5) --- Dificultad adaptativa (regla 3 de 4) ---
    # Guardamos las últimas 4 respuestas (1 = acierto, 0 = fallo)
    history = session.get("recent_results", [])
    history.append(1 if ok else 0)
    if len(history) > 4:
        history = history[-4:]
    session["recent_results"] = history

    # Ajuste de dificultad según el desempeño reciente
    # Límites dinámicos: min 1, max = máximo 'dif' presente en el banco
    try:
        max_dif_global = max(int(p["dif"]) for p in Preguntas.values())
    except Exception:
        max_dif_global = 3  # fallback conservador

    current_dif = int(session.get("selected_difficulty") or 1)

    if len(history) == 4:
        score = sum(history)  # aciertos en las últimas 4
        if score >= 3 and current_dif < max_dif_global:
            current_dif += 1
        elif score <= 1 and current_dif > 1:
            current_dif -= 1
        session["selected_difficulty"] = current_dif  # actualizar en sesión

    # 6) Respuesta al front
    return jsonify({
        "correct": ok,
        "message": "¡Correcto! ¿Deseas continuar?" if ok else "Incorrecta. ¿Deseas continuar?"
    })


@app.post("/api/next_question")
def next_question():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    data = request.get_json() or {}
    cont = bool(data.get("continue", False))
    if not cont:
        # Fin: mensaje y opción para volver al dashboard
        return jsonify({"end": True, "message": "¡Gracias por usar la app! Volverás al dashboard."})

    # Buscar otra pregunta del mismo tema, week <=, dif <= seleccionada, no repetida si fue correcta
    qid = pick_next_question(
        session["user_week"],
        session["selected_theme"],
        session["selected_difficulty"],
        session.get("answered_ok_ids") or []
    )
    if qid is None:
        return jsonify({"end": True, "message": "Terminaste todas las preguntas disponibles para este tema/dificultad."})

    session["current_qid"] = qid
    q = Preguntas[qid]
    return jsonify({
        "end": False,
        "question_id": qid,
        "html": q["enunciado_html"],
        "tema": q["tema"],
        "dif": q["dif"],
        "week": q["week"]
    })

@app.get("/api/history")
def history():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    con = get_db()
    rows = con.execute("""
        SELECT question_id, success, ts FROM interactions
        WHERE user_id = ?
        ORDER BY ts DESC
        LIMIT 200
    """, (session["user_id"],)).fetchall()
    con.close()
    return jsonify({
        "items": [
            {"question_id": r["question_id"], "success": bool(r["success"]), "ts": r["ts"]}
            for r in rows
        ]
    })

@app.get("/api/export/users_csv")
def export_users_csv():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    con = get_db()
    rows = con.execute("""
        SELECT id, full_name, email, uniandes_code, magistral, complementarios, created_at
        FROM users
        ORDER BY created_at DESC
    """).fetchall()
    con.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","full_name","email","uniandes_code","magistral","complementarios","created_at"])
    for r in rows:
        writer.writerow([r["id"], r["full_name"], r["email"], r["uniandes_code"], r["magistral"], r["complementarios"], r["created_at"]])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"}
    )

@app.get("/api/export/interactions_csv")
def export_interactions_csv():
    if not require_login():
        return jsonify({"error": "No autenticado"}), 401
    con = get_db()
    rows = con.execute("""
        SELECT i.user_id, u.email, i.question_id, i.success, i.ts
        FROM interactions i
        JOIN users u ON u.id = i.user_id
        ORDER BY i.ts DESC
    """).fetchall()
    con.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id","email","question_id","success","timestamp"])
    for r in rows:
        writer.writerow([r["user_id"], r["email"], r["question_id"], int(r["success"]), r["ts"]])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=interactions.csv"}
    )

# -----------------------------------
# Archivos estáticos del Front e imágenes del Back
# -----------------------------------
@app.route("/assets/<path:filename>")
def serve_assets(filename):
    # Sirve /assets/logo_uniandes.png, /assets/logo_facultad.png, /assets/salida.png
    return send_from_directory(IMAGES_DIR, filename)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_front(path):
    if path and os.path.exists(os.path.join(FRONT_DIR, path)):
        return send_from_directory(FRONT_DIR, path)
    return send_from_directory(FRONT_DIR, "index.html")


if __name__ == "__main__":
    import os
    # Usa el puerto que ponga Render si existiera; 5000 para local
    port = int(os.environ.get("PORT", "5000"))
    # Activa debug sólo si FLASK_DEBUG=1 (útil en local)
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)