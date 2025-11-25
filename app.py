# app.py
import os
import sqlite3
import string
import random
from urllib.parse import urlparse
from flask import Flask, g, render_template, request, redirect, url_for, flash

DB_PATH = os.getenv("DB_PATH", "urls.db")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "troque_isto_para_algo_secreto")

# ---------- DB helpers ----------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cur = conn.execute(query, args)
    conn.commit()
    cur.close()
    return cur.lastrowid

# ---------- Short code generation ----------
ALPHABET = string.ascii_letters + string.digits

def generate_code(length=6):
    return ''.join(random.choices(ALPHABET, k=length))

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc != ""
    except:
        return False

# ---------- Routes ----------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        original = request.form.get("original_url", "").strip()
        custom = request.form.get("custom_code", "").strip()
        if not is_valid_url(original):
            flash("URL inválida. Certifique-se de incluir http:// ou https://")
            return redirect(url_for("index"))

        # se fornceram código personalizado
        if custom:
            exists = query_db("SELECT * FROM urls WHERE code = ?", (custom,), one=True)
            if exists:
                flash("Código personalizado já existe. Tente outro.")
                return redirect(url_for("index"))
            code = custom
        else:
            # gerar até achar código não usado
            code = generate_code()
            tries = 0
            while query_db("SELECT * FROM urls WHERE code = ?", (code,), one=True):
                code = generate_code()
                tries += 1
                if tries > 10:
                    code = generate_code(8)  # aumenta se houver colisões

        execute_db(
            "INSERT INTO urls (code, original_url) VALUES (?, ?)",
            (code, original)
        )
        short = f"{BASE_URL.rstrip('/')}/{code}"
        return render_template("created.html", short=short, original=original, code=code)

    return render_template("index.html")

@app.route("/<code>")
def redirect_code(code):
    row = query_db("SELECT * FROM urls WHERE code = ?", (code,), one=True)
    if row:
        # opcional: incrementar contador
        try:
            execute_db("UPDATE urls SET hits = hits + 1 WHERE id = ?", (row["id"],))
        except:
            pass
        return redirect(row["original_url"])
    return ("Código não encontrado.", 404)

# ---------- CLI helper para criar DB ----------
def init_db():
    with app.app_context():
        conn = get_db()
        with open("schema.sql", "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        print("Banco inicializado.")

if __name__ == "__main__":
    # se quiser inicializar com python app.py initdb
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "initdb":
        init_db()
    else:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG", "1") == "1")
