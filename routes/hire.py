from flask import Blueprint, request, jsonify
from models.users import create_job

hirer_bp = Blueprint("hirer", __name__)

@hirer_bp.route("/post-job", methods=["POST"])
def post_job():
    data = request.get_json()
    job_id = create_job(data)
    return jsonify({"message": "Job submitted for approval", "job_id": job_id}), 201
