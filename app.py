from flask import Flask, render_template, request, redirect, session, send_file, send_from_directory
from functools import wraps
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from supabase_client import supabase
from uuid import uuid4

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

UPLOAD_FOLDER = "uploads/resumes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================
# LOGIN REQUIRED
# =========================
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("hr_logged_in"):
            return redirect("/")
        return f(*args, **kwargs)
    return wrap

# =========================
# AUTH (Temporary Basic Auth)
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            user = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            session["hr_logged_in"] = True
            session["user_email"] = email

            return redirect("/dashboard")

        except Exception as e:
            return "Invalid Login"

    return render_template("login.html")



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
@login_required
def dashboard():
    total_jobs = len(supabase.table("jobs").select("*").execute().data)
    total_applications = len(supabase.table("applications").select("*").execute().data)

    return render_template(
        "dashboard.html",
        total_jobs=total_jobs,
        total_applications=total_applications
    )

# =========================
# JOBS
# =========================
@app.route("/jobs", methods=["GET", "POST"])
@login_required
def jobs():

    if request.method == "POST":
        supabase.table("jobs").insert({
            "title": request.form["title"],
            "location": request.form["location"],
            "department": request.form.get("job_type"),
            "description": request.form["description"]
        }).execute()

    jobs = supabase.table("jobs").select("*").order("created_at", desc=True).execute().data
    return render_template("jobs.html", jobs=jobs)

@app.route("/delete-job/<job_id>")
@login_required
def delete_job(job_id):
    supabase.table("jobs").delete().eq("id", job_id).execute()
    return redirect("/jobs")

# =========================
# EDIT JOB
# =========================
@app.route("/edit-job/<job_id>", methods=["GET", "POST"])
@login_required
def edit_job(job_id):

    if request.method == "POST":
        supabase.table("jobs").update({
            "title": request.form["title"],
            "location": request.form["location"],
            "department": request.form.get("job_type"),
            "description": request.form["description"]
        }).eq("id", job_id).execute()

        return redirect("/jobs")

    job = supabase.table("jobs").select("*").eq("id", job_id).execute().data
    if not job:
        return "Job not found", 404

    return render_template("edit_job.html", job=job[0])

# =========================
# APPLY JOB
# =========================
@app.route("/apply/<job_id>", methods=["GET", "POST"])
def apply(job_id):

    job = supabase.table("jobs").select("*").eq("id", job_id).execute().data
    if not job:
        return "Job not found", 404

    if request.method == "POST":
        resume = request.files.get("resume")
        resume_url = None

        if resume and resume.filename:
            file_ext = resume.filename.split(".")[-1]
            file_name = f"{uuid4()}.{file_ext}"

            file_bytes = resume.read()

            supabase.storage.from_("resumes").upload(
                file_name,
                file_bytes,
                {"content-type": resume.content_type}
            )

            resume_url = supabase.storage.from_("resumes").get_public_url(file_name)

        supabase.table("applications").insert({
            "job_id": job_id,
            "name": request.form["name"],
            "email": request.form["email"],
            "phone": request.form["phone"],
            "resume_url": resume_url
        }).execute()

        return "Application submitted successfully!"

    return render_template("apply.html", job=job[0])
# =========================
# SETTINGS
# =========================
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():

    message = None

    if request.method == "POST":
        old = request.form.get("old_password")
        new = request.form.get("new_password")
        confirm = request.form.get("confirm_password")

        if new != confirm:
            message = "Passwords do not match"
        else:
            # Temporary password logic (since Supabase Auth not added yet)
            if old == "admin":
                message = "Password updated successfully (temporary login)"
            else:
                message = "Old password incorrect"

    return render_template("settings.html", message=message)

# =========================
# APPLICATIONS
# =========================
@app.route("/applications")
@login_required
def applications():

    jobs = supabase.table("jobs").select("id,title").execute().data
    applications = supabase.table("applications").select("*").execute().data

    return render_template(
        "applications.html",
        applications=applications,
        jobs=jobs
    )

# =========================
# EXCEL DOWNLOAD
# =========================
@app.route("/download-excel")
@login_required
def download_excel():

    apps = supabase.table("applications").select("*").execute().data
    df = pd.DataFrame(apps)

    file_path = "applications.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# =========================
# RESUME SERVE
# =========================
@app.route("/uploads/resumes/<path:filename>")
def serve_resume(filename):
    return send_from_directory("uploads/resumes", filename)

@app.route("/contact-us")
@login_required
def contact_us():
    contacts = supabase.table("contact_us") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute().data

    return render_template("contact_us.html", contacts=contacts)

# =========================
# ADD TEST CONTACT (FOR TESTING)
# =========================
@app.route("/contact-us/add", methods=["GET", "POST"])
@login_required
def add_contact_us():

    if request.method == "POST":
        supabase.table("contact_us").insert({
            "full_name": request.form["full_name"],
            "company": request.form.get("company"),
            "email": request.form["email"],
            "phone": request.form.get("phone"),
            "message": request.form["message"]
        }).execute()

        return redirect("/contact-us")

    return render_template("add_contact_us.html")

# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)