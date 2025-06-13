import jwt
from datetime import datetime, timedelta, timezone
import time
import threading
from flask import request, jsonify,Blueprint

auth = Blueprint('auth', __name__)

SECRET_KEY = "SUPER-SECRET-KEY"
REFRESH_SECRET = "SUPER-REFRESH-KEY"
active_tokens = {}
def generate_accesstoken(user_id):
    try:
        expiration_time = datetime.now(tz=timezone.utc) + timedelta(minutes=7)
        payload = {"user_id": user_id, "exp": expiration_time.timestamp()}
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        token_str = token if isinstance(token, str) else token.decode('utf-8')
        active_tokens[token_str] = expiration_time  
        return token_str, expiration_time
    except Exception as e:
        raise Exception(f"Error generating access token: {str(e)}")

user_refresh_tokens = {}

def generate_refresh_token(user_id):
    try:
        expiration_time = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
        payload = {"user_id": user_id, "exp": expiration_time.timestamp()}
        refresh_token = jwt.encode(payload, REFRESH_SECRET, algorithm="HS256")

        if isinstance(refresh_token, bytes):
            refresh_token = refresh_token.decode('utf-8')

        user_refresh_tokens[user_id] = {
            "refreshToken": refresh_token,
            "expires_at": expiration_time
        }

        return refresh_token, expiration_time
    except Exception as e:
        raise Exception(f"Error generating refresh token: {str(e)}")

def decode_token(token, secret=SECRET_KEY):
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired. Please log in again."
    except jwt.InvalidTokenError:
        return None, "Invalid token. Please log in again."
    except Exception as e:
        return None, f"Error decoding token: {str(e)}"

@auth.route('/refresh', methods=['POST'])
def refreshToken():
    try:
        data = request.get_json()
        if not data or not data.get("refreshToken"):
            return jsonify({"message": "Refresh token required"}), 400

        refreshToken = data.get("refreshToken")
        payload, error = decode_token(refreshToken, REFRESH_SECRET)
        if error:
            return jsonify({"message": error}), 401

        user_id = payload["user_id"]
        new_token, exp_time = generate_accesstoken(user_id)

        return jsonify({
            "access_token": new_token,
            "expires_in": "60 seconds"
        }), 200

    except Exception as e:
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

def monitor_token_expiry():
    try:
        while True:
            time.sleep(1)
            current_time = datetime.now(tz=timezone.utc)
            expired_tokens = [
                token for token, exp_time in active_tokens.items() if current_time > exp_time
            ]
            for token in expired_tokens:
                print(f"Token Expired: {token}")
                del active_tokens[token]
    except Exception as e:
        print(f"[Token Monitor Error] {str(e)}")

# Start the background thread safely
try:
    threading.Thread(target=monitor_token_expiry, daemon=True).start()
except Exception as e:
    print(f"[Thread Start Error] {str(e)}")