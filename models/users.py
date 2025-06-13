from extensions import db 
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from flask import Flask, request, jsonify
from supabase import create_client
import uuid
from werkzeug.utils import secure_filename




class Userss(db.Model):
    __tablename__ = 'userss'
    id = db.Column(db.Integer, primary_key=True)
    Emailid = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    userType=db.Column(db.String(100), nullable=False)



client = MongoClient("mongodb+srv://vijayprabakaran1905:Mongodbhirehub@cluster0.uma8of4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db_jobportal = client["job_portal"]
SUPABASE_URL="https://ravrvsezztusrbnynuhj.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJhdnJ2c2V6enR1c3JibnludWhqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NzQ2MTQ5NCwiZXhwIjoyMDYzMDM3NDk0fQ.anh2MgM_ekIGWgCQvV198GudwpHPxDQcbOh4YffiTVY"
SUPABASE_BUCKET="resumes"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def create_job(data):
    job = {
        "title": data["title"],
        "description": data["description"],
        "qualification": data["qualification"],  # e.g., BE
        "category": data["category"],            # e.g., IT
        "keywords": data.get("keywords", []),
        "status": "pending",
        "created_by": data["hirer_id"],
        "created_at": datetime.utcnow()
    }
    result = db_jobportal.jobs.insert_one(job)
    return str(result.inserted_id)


def approve_job(job_id):
    db_jobportal.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"status": "approved"}}
    )
    

def reject_job(job_id):
    try:
        db_jobportal.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "rejected"}}
        )
        return jsonify({"message": "Job rejected successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def search_jobs(filters):
    base_query = {"status": "approved"}
    conditions = []

    # Qualification filter (comma-separated values)
    if "qualification" in filters and filters["qualification"]:
        qualifications = [q.strip() for q in filters["qualification"].split(",")]
        conditions.append({"qualification": {"$in": qualifications}})

    # Keywords filter (assumed to be list)
    if "keywords" in filters and isinstance(filters["keywords"], list):
        conditions.append({"keywords": {"$in": filters["keywords"]}})

    # Title filter
    if "title" in filters and filters["title"]:
        conditions.append({"title": {"$regex": filters["title"], "$options": "i"}})

    # Category filter
    if "category" in filters and filters["category"]:
        conditions.append({"category": filters["category"]})

    # Final query: AND with status, OR with filters if multiple provided
    if conditions:
        query = {
            "$and": [
                base_query,
                {"$or": conditions}
            ]
        }
    else:
        query = base_query

    return list(db_jobportal.jobs.find(query))




def upload_resume(job_id):
    try:
        email = request.form.get("email")
        name = request.form.get("name")
        resume_file = request.files.get("resume")

        if not all([email, name, resume_file]):
            return jsonify({"error": "Missing required fields"}), 400

        # Check job existence
        job = db_jobportal.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Save to Supabase
        filename = f"{uuid.uuid4()}_{secure_filename(resume_file.filename)}"
        response = supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=resume_file.stream,
            file_options={"content-type": resume_file.mimetype}
        )

        if response.get("error"):
            return jsonify({"error": "Failed to upload resume"}), 500

        resume_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"

        # Store application in MongoDB
        db_jobportal.applications.insert_one({
            "job_id": job_id,
            "email": email,
            "name": name,
            "resume_url": resume_url,
            "uploaded_at": datetime.utcnow()
        })

        return jsonify({"message": "Resume uploaded successfully", "resume_url": resume_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




def get_resumes(job_id):
    try:
        applications = db_jobportal.applications.find({"job_id": job_id})
        result = []

        for app in applications:
            result.append({
                "name": app.get("name"),
                "email": app.get("email"),
                "resume_url": app.get("resume_url"),
                "uploaded_at": app.get("uploaded_at")
            })

        return jsonify({"resumes": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
