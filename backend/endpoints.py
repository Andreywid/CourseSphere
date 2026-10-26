from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from query_manager import QueryManager
from firebase import Firebase
from main import hashFunction

app = Flask(__name__)
CORS(app)

# TODO: figure out the blueprint thing below
#app.register_blueprint(courses_bp)

success_response = lambda data, code: (jsonify(data), code)
error_response = lambda error, code: (jsonify({'error': error}), code)

def get_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()

@app.route("/users/create", methods=["POST"])
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
        uid = Firebase.verify_id_token(id_token).get('uid')
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
        uid = Firebase.verify_id_token(id_token).get('uid') # !!!
        user_info = Firebase.get_user_info(uid)
        return success_response(user_info, 200)
    except Exception:
        app.logger.exception("GET /users/info failed")
        return error_response("Could not get user info", 400)
  
@app.route("/users/query", methods=["POST"])
def get_user_query():
    try:
        query = request.get_json().get("query")
        user_info = Firebase.try_get_user_info(request.get_json().get("id_token"))
        return success_response(QueryManager(query, user_info).response, 200)
    except Exception:
        app.logger.exception("POST /users/query failed")
        return error_response("Could not process query", 400)

@app.route('/hash', methods=['POST'])
def generate_message_id():
    id_token = get_bearer_token()
    if not id_token:
        return error_response("Missing or invalid Authorization header", 401)
    try:
        Firebase.verify_id_token(id_token).get('uid')
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
        user_id = Firebase.verify_id_token(id_token).get('uid')
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
        user_id = Firebase.verify_id_token(id_token).get('uid')
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
    app.run(debug=True)
