from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client
import os
import pandas as pd
from datetime import datetime

# =========================
# APP CONFIG
# =========================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")

# =========================
# SUPABASE CONFIG
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase credentials not set")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# AUTH
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        res = supabase.table("admins").select("*").eq("email", email).execute()

        if res.data and check_password_hash(res.data[0]["password"], password):
            session["hr_logged_in"] = True
            session["admin_email"] = email
            return redirect("/dashboard")

        return "Invalid login", 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if not session.get("hr_logged_in"):
        return redirect("/")

    jobs = supabase.table("jobs").select("*").execute().data
    applications = supabase.table("applications").select("*").execute().data

    return render_template(
        "dashboard.html",
        total_jobs=len(jobs),
        total_applications=len(applications)
    )

# =========================
# JOBS
# =========================
@app.route("/jobs", methods=["GET", "POST"])
def jobs():
    if not session.get("hr_logged_in"):
        return redirect("/")

    if request.method == "POST":
        supabase.table("jobs").insert({
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "location": request.form.get("location"),
            "job_type": request.form.get("job_type"),
            "posted_at": datetime.utcnow().date()
        }).execute()

    jobs = supabase.table("jobs").select("*").order("id", desc=True).execute().data
    return render_template("jobs.html", jobs=jobs)


@app.route("/delete-job/<int:id>")
def delete_job(id):
    if not session.get("hr_logged_in"):
        return redirect("/")

    supabase.table("jobs").delete().eq("id", id).execute()
    return redirect("/jobs")

# =========================
# APPLY JOB (SUPABASE STORAGE)
# =========================
@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
def apply(job_id):
    job = supabase.table("jobs").select("*").eq("id", job_id).execute().data

    if not job:
        return "Job not found", 404

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        resume = request.files.get("resume")

        if not all([name, email, phone, resume]):
            return "All fields required", 400

        filename = f"{job_id}_{int(datetime.utcnow().timestamp())}_{resume.filename}"

        # Upload resume
        supabase.storage.from_("resumes").upload(
            filename,
            resume.read(),
            {"content-type": resume.content_type}
        )

        resume_url = f"{SUPABASE_URL}/storage/v1/object/public/resumes/{filename}"

        supabase.table("applications").insert({
            "job_id": job_id,
            "applicant_name": name,
            "email": email,
            "phone": phone,
            "resume_url": resume_url
        }).execute()

        return "Application submitted successfully!"

    return render_template("apply.html", job=job[0])

# =========================
# APPLICATIONS
# =========================
@app.route("/applications")
def applications():
    if not session.get("hr_logged_in"):
        return redirect("/")

    selected_job = request.args.get("job_id")

    jobs = supabase.table("jobs").select("id,title").execute().data
    query = supabase.table("applications").select("*, jobs(title)")

    if selected_job:
        query = query.eq("job_id", selected_job)

    applications = query.execute().data

    return render_template(
        "applications.html",
        applications=applications,
        jobs=jobs,
        selected_job=selected_job
    )

# =========================
# EXPORT
# =========================
@app.route("/export-applications/<int:job_id>")
def export_filtered_applications(job_id):
    if not session.get("hr_logged_in"):
        return redirect("/")

    res = supabase.table("applications") \
        .select("applicant_name,email,phone") \
        .eq("job_id", job_id) \
        .execute()

    df = pd.DataFrame(res.data)
    file_path = "applications.xlsx"
    df.to_excel(file_path, index=False)
@app.route("/__reset_admin")
def reset_admin():
    db = get_db(dict_cursor=True)
    cur = db.cursor()

    hashed = generate_password_hash("admin123")

    cur.execute("""
        UPDATE admins
        SET password = %s
        WHERE email = %s
    """, (hashed, "admin@hr.com"))

    db.commit()
    db.close()
    return "Admin password reset to admin123"

    return send_file(file_path, as_attachment=True)
