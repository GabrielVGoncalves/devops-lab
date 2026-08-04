import os
import string
import random
import logging
from datetime import datetime
from flask import Flask, request, jsonify, redirect, abort

# ── Logging Setup ─────────────────────────────────────────────────────────────
# The logs/ directory is created automatically if it does not exist.
# In production, this file will be monitored by your observability stack (Phase 6).
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),   # file — read by Loki/ELK in Phase 6
        logging.StreamHandler()                 # stdout — captured by Docker in Phase 3
    ]
)
logger = logging.getLogger(__name__)

# ── Flask Application ─────────────────────────────────────────────────────────
app = Flask(__name__)

# In-memory database (simple to start with).
# In Phase 2 this will be replaced by PostgreSQL on AWS RDS.
db = {}


def generate_code(length=6):
    """Generates a random short code made of letters and digits."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=length))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    """
    Health check endpoint — used by load balancers, Kubernetes liveness probes,
    and monitoring tools (Phase 6 and Phase 7).
    Returns 200 if the application is healthy.
    """
    logger.info("healthcheck ok")
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@app.route("/shorten", methods=["POST"])
def shorten():
    """
    Shortens a URL.
    Receives: { "url": "https://example.com/very-long-path" }
    Returns:  { "short_code": "aB3xYz", "short_url": "/r/aB3xYz" }
    """
    data = request.get_json()

    if not data or "url" not in data:
        logger.warning("invalid request on /shorten — missing 'url' field")
        return jsonify({"error": "Please provide the 'url' field in the JSON body."}), 400

    original_url = data["url"]

    # Avoid duplicates: if the URL was already shortened, return the same code
    for code, url in db.items():
        if url == original_url:
            logger.info("existing url reused | code=%s url=%s", code, original_url)
            return jsonify({"short_code": code, "short_url": f"/r/{code}"})

    code = generate_code()
    while code in db:          # ensure uniqueness
        code = generate_code()

    db[code] = original_url
    logger.info("url shortened | code=%s url=%s", code, original_url)
    return jsonify({"short_code": code, "short_url": f"/r/{code}"}), 201


@app.route("/r/<code>")
def redirect_to(code):
    """
    Redirects to the original URL from the short code.
    Returns 404 if the code does not exist — tracked as an error in Phase 6.
    """
    original_url = db.get(code)

    if not original_url:
        logger.warning("code not found | code=%s ip=%s", code, request.remote_addr)
        abort(404)

    logger.info("redirect | code=%s destination=%s ip=%s",
                code, original_url, request.remote_addr)
    return redirect(original_url, code=302)


@app.route("/stats")
def stats():
    """
    Basic application statistics.
    Useful for validating the app and, later, exposing metrics to Prometheus (Phase 6).
    """
    logger.info("stats requested | total_urls=%d", len(db))
    return jsonify({
        "total_shortened_urls": len(db),
        "urls": {code: url for code, url in db.items()}
    })


# ── Error Handlers ────────────────────────────────────────────────────────────
# JSON error responses — standard for APIs. Error logs here
# will be counted as 4xx/5xx on the Grafana dashboard in Phase 6.

@app.errorhandler(404)
def not_found(e):
    logger.error("404 not found | path=%s", request.path)
    return jsonify({"error": "Resource not found."}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error("500 internal server error | path=%s error=%s", request.path, str(e))
    return jsonify({"error": "Internal server error."}), 500


# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info("application starting on port %d", port)
    app.run(host="0.0.0.0", port=port)