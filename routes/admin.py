from flask import Blueprint, request, jsonify
from models.users import approve_job,reject_job
admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/approve-job/<job_id>", methods=["POST"])
def approve(job_id):
    approve_job(job_id)
    return jsonify({"message": "Job approved"}), 200

@admin_bp.route("/reject_job/<job_id>", methods=["POST"])
def reject(job_id):
    reject_job(job_id)
    return jsonify({"message": "rejected"}), 200


