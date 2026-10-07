import os
import string
import random
import logging
import psycopg2
from datetime import datetime
from flask import Flask, request, jsonify, redirect, abort

# ── Logging Setup ─────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Flask Application ─────────────────────────────────────────────────────────
app = Flask(__name__)

db = {}

def generate_code(length=6):
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=length))

# ── Banco de métricas (Postgres) ───────────────────────────────────────────────

def get_connection():
    """Abre uma nova conexão com o Postgres usando variáveis de ambiente."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "postgres"),
        port=os.environ.get("DB_PORT", 5432),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "")
    )

def log_event(event_type, code=None, url=None, ip=None):
    """
    Grava um evento na tabela requests.
    Abre e fecha a conexão a cada chamada.
    Falhas aqui não devem derrubar a aplicação — só logamos o erro.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO requests (event_type, code, url, ip) VALUES (%s, %s, %s, %s);",
            (event_type, code, url, ip)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error("failed to log event to database | error=%s", str(e))

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    logger.info("healthcheck ok")
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json()

    if not data or "url" not in data:
        logger.warning("invalid request on /shorten — missing 'url' field")
        return jsonify({"error": "Please provide the 'url' field in the JSON body."}), 400

    original_url = data["url"]

    for code, url in db.items():
        if url == original_url:
            logger.info("existing url reused | code=%s url=%s", code, original_url)
            return jsonify({"short_code": code, "short_url": f"/r/{code}"})

    code = generate_code()
    while code in db:
        code = generate_code()

    db[code] = original_url
    logger.info("url shortened | code=%s url=%s", code, original_url)
    log_event("shorten", code=code, url=original_url, ip=request.remote_addr)
    return jsonify({"short_code": code, "short_url": f"/r/{code}"}), 201

@app.route("/r/<code>")
def redirect_to(code):
    original_url = db.get(code)

    if not original_url:
        logger.warning("code not found | code=%s ip=%s", code, request.remote_addr)
        log_event("404", code=code, ip=request.remote_addr)
        abort(404)

    logger.info("redirect | code=%s destination=%s ip=%s",
                code, original_url, request.remote_addr)
    log_event("redirect", code=code, url=original_url, ip=request.remote_addr)
    return redirect(original_url, code=302)

@app.route("/stats")
def stats():
    logger.info("stats requested | total_urls=%d", len(db))
    return jsonify({
        "total_shortened_urls": len(db),
        "urls": {code: url for code, url in db.items()}
    })

# ── Error Handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    logger.error("404 not found | path=%s", request.path)
    return jsonify({"error": "Resource not found."}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error("500 internal server error | path=%s error=%s", request.path, str(e))
    log_event("500", url=request.path)
    return jsonify({"error": "Internal server error."}), 500

# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info("application starting on port %d", port)
    app.run(host="0.0.0.0", port=port)