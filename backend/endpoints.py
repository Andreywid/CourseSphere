import logging
import os
import time
import uuid
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_flask_exporter import PrometheusMetrics
from pythonjsonlogger import jsonlogger
from werkzeug.exceptions import HTTPException
from query_manager import QueryManager
from firebase import Firebase
from main import hashFunction

app = Flask(__name__)
# CORS restricted to the frontend origin; Authorization must stay allowed for the token header.
CORS(
    app,
    origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_headers=["Content-Type", "Authorization"],
)

# Rate limiting for the endpoints the backend exposes (in-memory store, per client IP).
limiter = Limiter(get_remote_address, app=app)

@limiter.request_filter
def exempt_preflight():
    # CORS preflight must never be rate limited, or the browser flow breaks.
    return request.method == "OPTIONS"

# ---- Observability (Fase 6): structured JSON logs, metrics, health ----
# Logs go to stdout as JSON. The plain-text Werkzeug access log is dropped; the
# after_request line below is the per-request record.
_json_handler = logging.StreamHandler()
_json_handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
app.logger.handlers = [_json_handler]
app.logger.setLevel(logging.INFO)
app.logger.propagate = False
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# Prometheus metrics at /metrics: request count and latency by path and status.
# No auth, no rate limit. In production /metrics must sit on an internal network.
metrics = PrometheusMetrics(app)


@app.before_request
def _start_request():
    g.request_id = uuid.uuid4().hex
    g.start_time = time.perf_counter()


@app.after_request
def _log_request(response):
    # request.path never includes the query string, so no token can leak here.
    app.logger.info("request", extra={
        "event": "request",
        "request_id": getattr(g, "request_id", None),
        "method": request.method,
        "path": request.path,
        "route": request.url_rule.rule if request.url_rule else None,
        "status": response.status_code,
        "latency_ms": round((time.perf_counter() - getattr(g, "start_time", time.perf_counter())) * 1000, 2),
    })
    return response


@app.route("/health", methods=["GET"])
def health():
    return success_response({"status": "ok"}, 200)

# TODO: figure out the blueprint thing below
#app.register_blueprint(courses_bp)

success_response = lambda data, code: (jsonify(data), code)
error_response = lambda error, code: (jsonify({'error': error}), code)

def get_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()

class AuthError(Exception):
    pass

def verify_uid(id_token):
    # Verifies the Firebase ID token and logs the auth event. On failure it logs a
    # generic reason and raises AuthError, never the token or the provider's message
    # (which can echo the token). `from None` keeps that message out of the traceback.
    try:
        uid = Firebase.verify_id_token(id_token).get('uid')
    except Exception:
        app.logger.warning("auth failed", extra={"event": "auth", "result": "failure", "reason": "invalid_or_expired_token"})
        raise AuthError() from None
    app.logger.info("auth ok", extra={"event": "auth", "result": "success", "uid": uid})
    return uid

@app.route("/users/create", methods=["POST"])
@limiter.limit("5 per minute")
def create_user():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    if not email:
        return error_response("Email is required", 400)
    if not password:
        return error_response("Password is required", 400)
    try:
        return success_response(Firebase.create_user(email, password), 200)
    except Exception:
        app.logger.exception("POST /users/create failed")
        return error_response("Could not create user", 400)

@app.route("/users/info", methods=["POST"])
def set_user_info(): 
    data = request.get_json()
    id_token = data.get("id_token")
    try:
        uid = verify_uid(id_token)
        majors = data.get("majors")
        minors = data.get("minors")
        year = data.get("year")
        college = data.get("college")
        courses = data.get("courses")
        about = data.get("about")
        user_info = {
            "majors": majors,
            "minors": minors,
            "courses": courses,
            "college": college,
            "year": year,
            "about": about
        }
        Firebase.set_user_info(uid, user_info) 
        return success_response({"message": "User info set successfully", "uid": uid}, 200)
    except Exception:
        app.logger.exception("POST /users/info failed")
        return error_response("Could not save user info", 400)
        
@app.route("/users/info", methods=["GET"])
def get_user_info():
    id_token = get_bearer_token()
    if not id_token:
        return error_response("Missing or invalid Authorization header", 401)
    try:
        uid = verify_uid(id_token)
        user_info = Firebase.get_user_info(uid)
        return success_response(user_info, 200)
    except Exception:
        app.logger.exception("GET /users/info failed")
        return error_response("Could not get user info", 400)
  
@app.route("/users/query", methods=["POST"])
@limiter.limit("30 per minute")
def get_user_query():
    try:
        query = request.get_json().get("query")
        user_info = Firebase.try_get_user_info(request.get_json().get("id_token"))
        return success_response(QueryManager(query, user_info).response, 200)
    except Exception:
        app.logger.exception("POST /users/query failed")
        return error_response("Could not process query", 400)

@app.route('/hash', methods=['POST'])
@limiter.limit("60 per minute")
def generate_message_id():
    id_token = get_bearer_token()
    if not id_token:
        return error_response("Missing or invalid Authorization header", 401)
    try:
        verify_uid(id_token)
        data = request.get_json()
        message_id = hashFunction(data)
        return jsonify({'messageID': message_id}), 200
    except Exception:
        app.logger.exception("POST /hash failed")
        return error_response("Could not generate message ID", 500)

@app.route("/chats/<chat_id>/messages", methods=["POST"])
def save_chat(chat_id):
    id_token = get_bearer_token()
    if not id_token:
        return error_response("Missing or invalid Authorization header", 401)
    try:
        user_id = verify_uid(id_token)
        messages = request.get_json().get('messages', [])
        Firebase.save_chat(user_id, chat_id, messages)
        return jsonify({'message': 'Messages saved successfully'}), 200
    except Exception:
        app.logger.exception("POST /chats/<chat_id>/messages failed")
        return error_response("Could not save messages", 400)

@app.route("/chats/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    id_token = get_bearer_token()
    if not id_token:
        return error_response("Missing or invalid Authorization header", 401)
    try:
        user_id = verify_uid(id_token)
        Firebase.delete_chat(user_id, chat_id)
        return success_response({'message': 'Message deleted successfully'}, 200)
    except Exception:
        app.logger.exception("DELETE /chats/<chat_id> failed")
        return error_response("Could not delete chat", 400)

# HTTPExceptions (404, 405, 415...) keep their own status; only unexpected errors become a generic 500.
@app.errorhandler(Exception)
def handle_unexpected(e):
    if isinstance(e, HTTPException):
        return e
    app.logger.exception("Unhandled exception")
    return error_response("Internal server error", 500)


if __name__ == '__main__':
    # Debug is off by default; set FLASK_DEBUG=1 to enable it locally (never in a deployed env).
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
