from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
from apis.user_access import user_access_bp
from utils.auth import auth
from routes.admin import admin_bp
from routes.candidate import candidate_bp
from routes.hire import hirer_bp
from extensions import db
from utils.auth import decode_token, active_tokens  
from utils.chatgroq import chatgroq_bp


EXEMPT_ROUTES = ['/register', '/login', '/refresh','/progress']  

def create_app():
    app = Flask(__name__)
    CORS(app) 
    CORS(app, resources={r"/*": {"origins": "*"}})
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
    

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(user_access_bp)
    app.register_blueprint(hirer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(chatgroq_bp)


    # app.register_blueprint(search_selection)

    @app.before_request
    def verify_token_before_request():
        try:
            if request.method == "OPTIONS":
                return

            if request.path in EXEMPT_ROUTES:
                return

            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return jsonify({"message": "Missing token"}), 401

            token = auth_header.split(" ")[1] if " " in auth_header else auth_header

            if token not in active_tokens or datetime.now(tz=timezone.utc) > active_tokens[token]:
                return jsonify({"message": "Token is invalid or expired."}), 401

            try:
                payload, error = decode_token(token)
            except Exception as decode_err:
                return jsonify({"message": "Failed to decode token", "error": str(decode_err)}), 401

            if error:
                return jsonify({"message": error}), 401

            request.user = payload

        except Exception as e:
            return jsonify({"message": "Internal server error", "error": str(e)}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
    # app.run(host='172.24.219.141', port=5000, debug=True)
