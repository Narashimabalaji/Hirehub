from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import fitz  # PyMuPDF
import os
import requests
import re

chatgroq_bp = Blueprint("chatgroq", __name__)

# --- Config ---
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama3-70b-8192"

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- MongoDB ---
client = MongoClient("mongodb://localhost:27017/")
db = client["job_portal"]
jobs_collection = db.jobs

# --- Utilities ---

def is_greeting(text):
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy", "hola"]
    text = text.lower()
    return any(greet in text for greet in greetings)

def is_who_are_you_question(text):
    lower = text.lower()
    return "who are you" in lower or "what are you" in lower

def extract_text_from_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        current_app.logger.error(f"Failed to extract text from PDF: {e}")
        return ""

def fetch_jobs_matching(text_input=None, filters=None):
    query = {"status": "approved"}

    # --- When filters are explicitly provided ---
    if filters:
        if "qualification" in filters and filters["qualification"]:
            qualifications = [q.strip() for q in filters["qualification"].split(",")]
            query["qualification"] = {"$in": qualifications}

        if "keywords" in filters and isinstance(filters["keywords"], list):
            query["keywords"] = {"$in": filters["keywords"]}

        if "category" in filters and filters["category"]:
            query["category"] = filters["category"]

        if "title" in filters and filters["title"]:
            query["title"] = {"$regex": filters["title"], "$options": "i"}

    # --- When raw text is provided (like from question/resume) ---
    elif text_input:
        keywords = set(re.findall(r'\w+', text_input.lower()))
        if keywords:
            regex_pattern = "|".join(re.escape(word) for word in keywords)
            query["$or"] = [
                {"qualification": {"$regex": regex_pattern, "$options": "i"}},
                {"description": {"$regex": regex_pattern, "$options": "i"}},
                {"title": {"$regex": regex_pattern, "$options": "i"}},
                {"keywords": {"$in": list(keywords)}},
            ]

    return list(jobs_collection.find(query).limit(10))


def build_prompt(user_question, resume_text=None, job_list=None):
    system_msg = (
        "You are a helpful AI assistant. "
        "Only use the provided job listings from the database to answer the user's question. "
        "Do not make up any job openings or qualifications. If a qualification matches, explain clearly which jobs match."
    )

    resume_section = f"User Resume:\n{resume_text}" if resume_text else "No resume provided."

    if job_list:
        jobs_info = "\n".join(
            [
                f"{i+1}. Title: {job.get('title')}\n"
                f"   Company: {job.get('company_name', 'Unknown')}\n"
                f"   Qualification Required: {job.get('qualification', 'N/A')}\n"
                f"   Description: {job.get('description', 'N/A')}\n"
                for i, job in enumerate(job_list)
            ]
        )
    else:
        jobs_info = "No job matches found in the database."

    user_prompt = (
        f"{resume_section}\n\n"
        f"Available Job Listings:\n{jobs_info}\n\n"
        f"User Question: {user_question}\n\n"
        f"Answer based strictly on the listings above. "
        f"If any job matches the user's qualification, mention them specifically. "
        f"Do not say no jobs exist unless the job list above is empty."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_prompt}
    ]

def chat_with_groq(messages):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        current_app.logger.error(f"Groq API Error: {e}")
        return "Sorry, I couldn't get a response from the AI."

# --- Routes ---

@chatgroq_bp.route("/chat", methods=["POST"])
def chat():
    data = request.json
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question is required."}), 400

    # --- Static replies for greetings ---
    if is_greeting(question):
        return jsonify({
            "matched_jobs": [],
            "response": "Hello! I'm Nava, your job assistant bot at HireHub. How can I help you today?"
        })

    if is_who_are_you_question(question):
        return jsonify({
            "matched_jobs": [],
            "response": "I'm Nava, a job finder assistant here at HireHub. Feel free to ask me anything about job openings or your resume."
        })

    filters = data.get("filters", {})

    jobs = fetch_jobs_matching(text_input=question, filters=filters)
    prompt = build_prompt(question, resume_text=None, job_list=jobs)
    ai_response = chat_with_groq(prompt)

    return jsonify({
        "matched_jobs": [job.get("title") for job in jobs],
        "response": ai_response
    })

@chatgroq_bp.route("/upload_resume_and_chat", methods=["POST"])
def upload_resume_and_chat():
    question = request.form.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    if 'resume' not in request.files:
        return jsonify({"error": "No resume file uploaded."}), 400

    resume_file = request.files['resume']
    filename = secure_filename(resume_file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:
        resume_file.save(filepath)
        resume_text = extract_text_from_pdf(filepath)
        os.remove(filepath)  # clean up uploaded file after extracting text

        # Static replies for greetings or identity questions on resume upload chat
        if is_greeting(question):
            return jsonify({
                "matched_jobs": [],
                "response": "Hello! I'm Nava, your job assistant bot at HireHub. How can I help you today?"
            })

        if is_who_are_you_question(question):
            return jsonify({
                "matched_jobs": [],
                "response": "I'm Nava, a job finder assistant here at HireHub. Feel free to ask me anything about job openings or your resume."
            })

        jobs = fetch_jobs_matching(resume_text)
        prompt = build_prompt(question, resume_text, jobs)
        ai_response = chat_with_groq(prompt)

        return jsonify({
            "matched_jobs": [job.get("title") for job in jobs],
            "response": ai_response
        })

    except Exception as e:
        current_app.logger.error(f"Error processing resume and chat: {e}")
        return jsonify({"error": "Failed to process the resume and chat."}), 500
