"""PlacePilot AI: AI-powered college placement management system (Flask + SQLite).

Run:  python app.py      then open http://127.0.0.1:5000
On Vercel the platform imports `app` from this file; see the README.
"""
from __future__ import annotations

import io
import os
import re
import secrets
import sqlite3
from datetime import date
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

import analytics
import config
import database
import readiness_model
import seed
from ai_engine import SKILLS, Engine, Semantic, eligibility, extract_skills, normalize_list, normalize_skill, split_list

WEB_DIR = config.BASE_DIR / "web"
DEPTS = ["CSE", "IT", "AI&DS", "ECE", "EEE", "MECH"]
STATUSES = ["Applied", "Shortlisted", "Interview", "Offered", "Rejected"]
JOB_TYPES = ["Full-time", "Internship"]
ITEM_TABLES = {"projects": "projects", "certs": "certifications", "exp": "experience"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _secret_key() -> str:
    """Use PLACEPILOT_SECRET if set, otherwise keep one random key on disk so logins survive restarts.

    On a host with temporary storage (config.EPHEMERAL) always set PLACEPILOT_SECRET: every copy
    of the app would otherwise invent its own key and people would be signed out at random.
    """
    if os.environ.get("PLACEPILOT_SECRET"):
        return os.environ["PLACEPILOT_SECRET"]
    if config.EPHEMERAL:
        print("WARNING: PLACEPILOT_SECRET is not set. Logins will not survive restarts on this host.")
    path = config.DATA_DIR / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


app = Flask(__name__, static_folder=None)
app.config.update(SECRET_KEY=_secret_key(), MAX_CONTENT_LENGTH=4 * 1024 * 1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.json.sort_keys = False

database.init_db()
semantic = Semantic()
_readiness = None


def readiness() -> readiness_model.ReadinessModel:
    global _readiness
    if _readiness is None:
        _readiness = readiness_model.load_or_train()
    return _readiness


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message, self.status = message, status


@app.errorhandler(ApiError)
def _api_error(err: ApiError):
    return jsonify(error=err.message), err.status


@app.errorhandler(HTTPException)
def _http_error(err: HTTPException):
    if request.path.startswith("/api/"):
        message = "That file is larger than 4 MB. Choose a smaller one." if err.code == 413 else err.description
        return jsonify(error=message), err.code
    return err


@app.errorhandler(sqlite3.IntegrityError)
def _integrity_error(err):
    return jsonify(error="That change conflicts with existing data."), 400


def conn() -> sqlite3.Connection:
    if "conn" not in g:
        g.conn = database.connect()
    return g.conn


@app.teardown_appcontext
def _close(_exc):
    c = g.pop("conn", None)
    if c is not None:
        c.close()


def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    row = conn().execute("SELECT id, role, name, email, title FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None:
        session.clear()
    return row


def login_required(role: str | None = None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                raise ApiError("Sign in to continue.", 401)
            if role and user["role"] != role:
                raise ApiError("Your account cannot do that.", 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def text(data: dict, key: str, label: str, required: bool = False, maxlen: int = 200) -> str:
    value = re.sub(r"[ \t]+", " ", str(data.get(key) or "")).strip()[:maxlen]
    if required and not value:
        raise ApiError(f"{label} is required.")
    return value


def number(data: dict, key: str, label: str, lo: float, hi: float, default=None, integer: bool = False):
    raw = data.get(key)
    if raw is None or str(raw).strip() == "":
        if default is None:
            raise ApiError(f"{label} is required.")
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ApiError(f"{label} must be a number.")
    if not lo <= value <= hi:
        raise ApiError(f"{label} must be between {lo:g} and {hi:g}.")
    return int(value) if integer else value


def as_id(value, label: str = "Record") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{label} not found.", 404)


def engine() -> Engine:
    return Engine(database.load_data(conn()), semantic, readiness())


def find(items: list[dict], item_id) -> dict | None:
    return next((x for x in items if x["id"] == str(item_id)), None)


def ranked(eng: Engine, matches: dict) -> list[dict]:
    """Open roles for one student: eligible first, then by score."""
    return sorted((matches[j["id"]] for j in eng.open_jobs), key=lambda m: (not m["elig"]["ok"], -m["score"]))


def meta() -> dict:
    return {"skills": [[s[0], s[1]] for s in SKILLS], "semantic": semantic.info(), "readiness": readiness().meta,
            "today": date.today().isoformat(), "depts": DEPTS, "ephemeral": config.EPHEMERAL}


def preview() -> dict | None:
    """The sample match shown on the sign-in screen. Only ever uses the demo student."""
    eng = engine()
    st = next((s for s in eng.students if s["email"] == seed.DEMO_STUDENT_EMAIL), None)
    if st is None or not eng.open_jobs:
        return None
    matches = eng.match_all(st)
    top = ranked(eng, matches)[0]
    job = find(eng.jobs, top["jobId"])
    out = {"student": st["name"], "title": job["title"], "company": eng.companies.get(job["companyId"], {}).get("name", ""),
           "pay": job["pay"], "score": top["score"], "rows": top["rows"][:7], "tip": None}
    gap = next((r for r in top["rows"] if r["c"] < 1), None)
    if gap:
        out["tip"] = {"skill": gap["skill"], "to": eng.match_all(st, [gap["skill"]])[job["id"]]["score"]}
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    response = send_from_directory(WEB_DIR, "index.html")
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
@app.post("/api/login")
def login():
    data = body()
    email = text(data, "email", "Email").lower()
    row = conn().execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], str(data.get("pass") or "")):
        raise ApiError("That email and password do not match an account. Try a demo account below.", 401)
    session.clear()
    session["uid"] = row["id"]
    session.permanent = True
    return jsonify(ok=True)


@app.post("/api/register")
def register():
    data = body()
    name = text(data, "name", "Full name")
    email = text(data, "email", "Email").lower()
    password = str(data.get("pass") or "")
    if len(name) < 2:
        raise ApiError("Enter your full name.")
    if not EMAIL_RE.match(email):
        raise ApiError("Enter a valid email address.")
    if conn().execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise ApiError("An account with that email already exists. Sign in instead.")
    if data.get("dept") not in DEPTS:
        raise ApiError("Choose your department.")
    cgpa = number(data, "cgpa", "CGPA", 0, 10)
    if len(password) < 8:
        raise ApiError("Choose a password with at least 8 characters.")
    uid = database.create_student(conn(), name, email, password, data["dept"], cgpa)
    conn().commit()
    session.clear()
    session["uid"] = uid
    session.permanent = True
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/state")
def state():
    """Everything the front end needs for the signed-in user, with all scores computed here."""
    user = current_user()
    if user is None:
        return jsonify(session=None, preview=preview(), meta=meta())
    eng = engine()
    uid = str(user["id"])
    if user["role"] == "student":
        me = find(eng.students, uid)
        matches = eng.match_all(me)
        return jsonify(
            session={"role": "student", "id": uid}, me=me,
            db={"students": [me], "companies": list(eng.companies.values()), "jobs": eng.jobs,
                "applications": [a for a in eng.applications if a["studentId"] == uid]},
            matches={uid: matches}, readiness={uid: eng.readiness(me, matches)}, roadmap=eng.roadmap(me, matches),
            demand=eng.demand(), meta=meta())
    matches = eng.match_many(eng.students)
    scores = {s["id"]: eng.readiness(s, matches[s["id"]]) for s in eng.students}
    demand = eng.demand()
    data = {"students": eng.students, "companies": list(eng.companies.values()), "jobs": eng.jobs, "applications": eng.applications}
    return jsonify(
        session={"role": "officer", "id": uid},
        me={"id": uid, "name": user["name"], "email": user["email"], "title": user["title"]},
        db=data, matches=matches, readiness=scores, roadmap=[], demand=demand,
        overview=analytics.overview(data, matches, scores, demand, eng.today), meta=meta())


# ---------------------------------------------------------------------------
# Student: profile
# ---------------------------------------------------------------------------
@app.put("/api/me/profile")
@login_required("student")
def update_profile():
    data, sid = body(), g.user["id"]
    name = text(data, "name", "Full name")
    if len(name) < 2:
        raise ApiError("Enter your full name.")
    if data.get("dept") not in DEPTS:
        raise ApiError("Choose your department.")
    conn().execute("UPDATE users SET name = ? WHERE id = ?", (name, sid))
    conn().execute(
        "UPDATE students SET dept = ?, cgpa = ?, backlogs = ?, grad_year = ?, phone = ?, tenth = ?, twelfth = ?, headline = ? WHERE user_id = ?",
        (data["dept"], number(data, "cgpa", "CGPA", 0, 10), number(data, "backlogs", "Active backlogs", 0, 30, 0, integer=True),
         number(data, "gradYear", "Graduation year", 2020, 2035, 2027, integer=True), text(data, "phone", "Phone", maxlen=20),
         text(data, "tenth", "Class 10", maxlen=6), text(data, "twelfth", "Class 12", maxlen=6), text(data, "headline", "About you", maxlen=600), sid))
    conn().commit()
    return jsonify(ok=True)


@app.post("/api/me/skills")
@login_required("student")
def add_skills():
    result = database.add_student_skills(conn(), g.user["id"], str(body().get("text") or "")[:1000])
    conn().commit()
    return jsonify(result)


@app.post("/api/me/skills/remove")
@login_required("student")
def remove_skill():
    conn().execute("DELETE FROM student_skills WHERE student_id = ? AND skill = ?", (g.user["id"], str(body().get("skill") or "")))
    conn().commit()
    return jsonify(ok=True)


@app.post("/api/me/items/<kind>")
@login_required("student")
def add_item(kind: str):
    data, sid = body(), g.user["id"]
    if kind == "projects":
        conn().execute("INSERT INTO projects (student_id, title, description, tech) VALUES (?,?,?,?)",
                       (sid, text(data, "title", "Project title", True), text(data, "desc", "Description", maxlen=1200),
                        database.json.dumps(normalize_list(str(data.get("tech") or "")[:400]))))
    elif kind == "certs":
        conn().execute("INSERT INTO certifications (student_id, name, issuer) VALUES (?,?,?)",
                       (sid, text(data, "name", "Certificate name", True), text(data, "issuer", "Issuer") or "Not specified"))
    elif kind == "exp":
        conn().execute("INSERT INTO experience (student_id, role, org, months, description) VALUES (?,?,?,?,?)",
                       (sid, text(data, "role", "Role", True), text(data, "org", "Organisation") or "Not specified",
                        number(data, "months", "Duration", 1, 60, 1, integer=True), text(data, "desc", "Description", maxlen=1200)))
    else:
        raise ApiError("Unknown profile section.", 404)
    conn().commit()
    return jsonify(ok=True)


@app.delete("/api/me/items/<kind>/<int:item_id>")
@login_required("student")
def delete_item(kind: str, item_id: int):
    if kind not in ITEM_TABLES:
        raise ApiError("Unknown profile section.", 404)
    conn().execute(f"DELETE FROM {ITEM_TABLES[kind]} WHERE id = ? AND student_id = ?", (item_id, g.user["id"]))
    conn().commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# Student: resume
# ---------------------------------------------------------------------------
@app.post("/api/me/resume/extract")
@login_required("student")
def extract_resume():
    """Read the text out of an uploaded PDF or text file. Nothing is saved until the student confirms."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise ApiError("Choose a file to upload.")
    raw, name = upload.read(), upload.filename
    try:
        if name.lower().endswith(".pdf") or upload.mimetype == "application/pdf":
            from pypdf import PdfReader
            content = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(raw)).pages)
        else:
            content = raw.decode("utf-8", errors="ignore")
    except Exception:
        content = ""
    content = re.sub(r"[ \t]+", " ", content.replace("\x00", "")).strip()
    if not content:
        raise ApiError("Could not read text from this file. Paste your resume text into the box instead.", 422)
    return jsonify(text=content[:20000], name=Path(name).name[:120])


@app.post("/api/me/resume")
@login_required("student")
def save_resume():
    data = body()
    content = str(data.get("text") or "").strip()[:20000]
    if len(content) < 40:
        raise ApiError("Paste or upload your resume text first (at least a few lines).")
    conn().execute("UPDATE students SET resume_name = ?, resume_text = ?, resume_date = ? WHERE user_id = ?",
                   (text(data, "name", "File name", maxlen=120) or "Pasted text", content, date.today().isoformat(), g.user["id"]))
    conn().commit()
    return jsonify(found=extract_skills(content))


@app.delete("/api/me/resume")
@login_required("student")
def delete_resume():
    conn().execute("UPDATE students SET resume_name = NULL, resume_text = NULL, resume_date = NULL WHERE user_id = ?", (g.user["id"],))
    conn().commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------
@app.post("/api/simulate")
@login_required("student")
def simulate():
    """What-If Simulator: re-score every role as if the student also had these skills."""
    eng = engine()
    me = find(eng.students, g.user["id"])
    add = [k for k in normalize_list(list(body().get("add") or [])[:15]) if k not in me["skills"]]
    return jsonify(add=add, **eng.simulate(me, add))


@app.post("/api/normalize")
@login_required()
def normalize():
    return jsonify(skills=[n for n in (normalize_skill(x) for x in split_list(str(body().get("text") or "")[:400])) if n])


@app.post("/api/extract-skills")
@login_required()
def extract():
    data = body()
    found = extract_skills(str(data.get("text") or "")[:20000])
    listed = normalize_list(str(data.get("listed") or "")[:2000])
    return jsonify(found=found, fresh=[k for k in found if k not in listed])


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
@app.post("/api/applications")
@login_required("student")
def apply():
    eng = engine()
    me, job = find(eng.students, g.user["id"]), find(eng.jobs, body().get("jobId"))
    if job is None:
        raise ApiError("That role no longer exists.", 404)
    if job not in eng.open_jobs:
        raise ApiError("Applications for this role have closed.")
    if not eligibility(me, job)["ok"]:
        raise ApiError("You do not meet the eligibility criteria for this role.")
    if any(a["studentId"] == me["id"] and a["jobId"] == job["id"] for a in eng.applications):
        raise ApiError("You have already applied to this role.")
    today = date.today().isoformat()
    conn().execute("INSERT INTO applications (student_id, job_id, status, applied_on, updated_on) VALUES (?, ?, 'Applied', ?, ?)",
                   (g.user["id"], int(job["id"]), today, today))
    conn().commit()
    return jsonify(ok=True)


@app.delete("/api/applications/<int:app_id>")
@login_required("student")
def withdraw(app_id: int):
    row = conn().execute("SELECT status FROM applications WHERE id = ? AND student_id = ?", (app_id, g.user["id"])).fetchone()
    if row is None:
        raise ApiError("Application not found.", 404)
    if row["status"] != "Applied":
        raise ApiError("This application has already moved forward and cannot be withdrawn here.")
    conn().execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn().commit()
    return jsonify(ok=True)


@app.put("/api/applications/<int:app_id>")
@login_required("officer")
def set_status(app_id: int):
    status = body().get("status")
    if status not in STATUSES:
        raise ApiError("Choose a valid stage.")
    done = conn().execute("UPDATE applications SET status = ?, updated_on = ? WHERE id = ?", (status, date.today().isoformat(), app_id)).rowcount
    conn().commit()
    if not done:
        raise ApiError("Application not found.", 404)
    return jsonify(ok=True)


@app.post("/api/shortlist")
@login_required("officer")
def shortlist():
    data, eng = body(), engine()
    st, job = find(eng.students, data.get("studentId")), find(eng.jobs, data.get("jobId"))
    if st is None or job is None:
        raise ApiError("Student or role not found.", 404)
    if not eligibility(st, job)["ok"]:
        raise ApiError("This student does not meet the eligibility criteria.")
    today = date.today().isoformat()
    existing = next((a for a in eng.applications if a["studentId"] == st["id"] and a["jobId"] == job["id"]), None)
    if existing is None:
        conn().execute("INSERT INTO applications (student_id, job_id, status, applied_on, updated_on) VALUES (?, ?, 'Shortlisted', ?, ?)",
                       (int(st["id"]), int(job["id"]), today, today))
    elif existing["status"] == "Applied":
        conn().execute("UPDATE applications SET status = 'Shortlisted', updated_on = ? WHERE id = ?", (today, int(existing["id"])))
    conn().commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# Officer: students
# ---------------------------------------------------------------------------
def _student_fields(data: dict, exclude_id: int | None = None) -> dict:
    name = text(data, "name", "Full name", True)
    email = text(data, "email", "Email", True).lower()
    if not EMAIL_RE.match(email):
        raise ApiError("Enter a valid email address.")
    clash = conn().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if clash and clash["id"] != exclude_id:
        raise ApiError("Another account already uses that email.")
    if data.get("dept") not in DEPTS:
        raise ApiError("Choose a department.")
    return {"name": name, "email": email, "dept": data["dept"], "cgpa": number(data, "cgpa", "CGPA", 0, 10),
            "backlogs": number(data, "backlogs", "Active backlogs", 0, 30, 0, integer=True),
            "grad_year": number(data, "gradYear", "Graduation year", 2020, 2035, 2027, integer=True),
            "skills": normalize_list(str(data.get("skills") or "")[:2000])}


@app.post("/api/students")
@login_required("officer")
def create_student():
    f = _student_fields(body())
    temp_password = secrets.token_urlsafe(6)
    sid = database.create_student(conn(), f["name"], f["email"], temp_password, f["dept"], f["cgpa"], f["backlogs"], f["grad_year"])
    database.set_student_skills(conn(), sid, f["skills"])
    conn().commit()
    return jsonify(id=str(sid), tempPassword=temp_password)


@app.put("/api/students/<int:sid>")
@login_required("officer")
def update_student(sid: int):
    if conn().execute("SELECT 1 FROM students WHERE user_id = ?", (sid,)).fetchone() is None:
        raise ApiError("Student not found.", 404)
    f = _student_fields(body(), exclude_id=sid)
    conn().execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (f["name"], f["email"], sid))
    conn().execute("UPDATE students SET dept = ?, cgpa = ?, backlogs = ?, grad_year = ? WHERE user_id = ?",
                   (f["dept"], f["cgpa"], f["backlogs"], f["grad_year"], sid))
    database.set_student_skills(conn(), sid, f["skills"])
    conn().commit()
    return jsonify(ok=True)


@app.delete("/api/students/<int:sid>")
@login_required("officer")
def delete_student(sid: int):
    conn().execute("DELETE FROM users WHERE id = ? AND role = 'student'", (sid,))
    conn().commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# Officer: companies
# ---------------------------------------------------------------------------
def _company_fields(data: dict) -> tuple:
    return (text(data, "name", "Company name", True), text(data, "sector", "Sector"), text(data, "location", "Location"),
            text(data, "about", "About", maxlen=800))


@app.post("/api/companies")
@login_required("officer")
def create_company():
    cid = conn().execute("INSERT INTO companies (name, sector, location, about) VALUES (?,?,?,?)", _company_fields(body())).lastrowid
    conn().commit()
    return jsonify(id=str(cid))


@app.put("/api/companies/<int:cid>")
@login_required("officer")
def update_company(cid: int):
    done = conn().execute("UPDATE companies SET name = ?, sector = ?, location = ?, about = ? WHERE id = ?", (*_company_fields(body()), cid)).rowcount
    conn().commit()
    if not done:
        raise ApiError("Company not found.", 404)
    return jsonify(ok=True)


@app.delete("/api/companies/<int:cid>")
@login_required("officer")
def delete_company(cid: int):
    removed = conn().execute("SELECT COUNT(*) FROM jobs WHERE company_id = ?", (cid,)).fetchone()[0]
    conn().execute("DELETE FROM companies WHERE id = ?", (cid,))
    conn().commit()
    return jsonify(ok=True, jobsRemoved=removed)


# ---------------------------------------------------------------------------
# Officer: job postings
# ---------------------------------------------------------------------------
def _job_fields(data: dict) -> tuple[tuple, list[str], list[str]]:
    company_id = as_id(data.get("companyId"), "Company")
    if conn().execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone() is None:
        raise ApiError("Choose a company.")
    title, pay = text(data, "title", "Role title", True), text(data, "pay", "Package", True, 60)
    desc = text(data, "desc", "Job description", True, 4000)
    if data.get("type") not in JOB_TYPES:
        raise ApiError("Choose a role type.")
    depts = [d for d in (data.get("depts") or []) if d in DEPTS]
    if not depts:
        raise ApiError("Select at least one eligible department.")
    deadline = str(data.get("deadline") or "")
    try:
        date.fromisoformat(deadline)
    except ValueError:
        raise ApiError("Choose an application deadline.")
    must = normalize_list(str(data.get("must") or "")[:2000])
    nice = [k for k in normalize_list(str(data.get("nice") or "")[:2000]) if k not in must]
    if not must:
        raise ApiError("List at least one must-have skill.")
    row = (company_id, title, data["type"], number(data, "ctc", "Annual value", 0, 500, 0), pay, text(data, "location", "Location"),
           number(data, "minCgpa", "Minimum CGPA", 0, 10, 0), number(data, "maxBacklogs", "Backlogs allowed", 0, 20, 0, integer=True),
           database.json.dumps(depts), number(data, "openings", "Openings", 1, 1000, 1, integer=True), deadline, desc)
    return row, must, nice


@app.post("/api/jobs")
@login_required("officer")
def create_job():
    row, must, nice = _job_fields(body())
    jid = conn().execute(
        "INSERT INTO jobs (company_id, title, type, ctc, pay, location, min_cgpa, max_backlogs, depts, openings, deadline, description) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        row).lastrowid
    database.set_job_skills(conn(), jid, must, nice)
    conn().commit()
    return jsonify(id=str(jid))


@app.put("/api/jobs/<int:jid>")
@login_required("officer")
def update_job(jid: int):
    row, must, nice = _job_fields(body())
    done = conn().execute(
        "UPDATE jobs SET company_id = ?, title = ?, type = ?, ctc = ?, pay = ?, location = ?, min_cgpa = ?, max_backlogs = ?, depts = ?, openings = ?, deadline = ?, description = ? WHERE id = ?",
        (*row, jid)).rowcount
    if not done:
        raise ApiError("Job posting not found.", 404)
    database.set_job_skills(conn(), jid, must, nice)
    conn().commit()
    return jsonify(ok=True)


@app.delete("/api/jobs/<int:jid>")
@login_required("officer")
def delete_job(jid: int):
    conn().execute("DELETE FROM jobs WHERE id = ?", (jid,))
    conn().commit()
    return jsonify(ok=True)


@app.post("/api/reset")
@login_required("officer")
def reset():
    """Wipe the database and reload the sample students, companies and roles."""
    g.pop("conn").close()
    database.init_db(reset=True)
    officer = conn().execute("SELECT id FROM users WHERE email = ?", (seed.DEMO_OFFICER_EMAIL,)).fetchone()
    session.clear()
    session["uid"] = officer["id"]
    return jsonify(ok=True)


if __name__ == "__main__":
    info = semantic.info()
    print(f"Semantic engine : {info['model']}" + (f"  (fallback: {info['fallbackReason']})" if info["fallbackReason"] else ""))
    m = readiness().meta
    print(f"Readiness model : {m['algorithm']}, {m['rows']} rows from {m['source']}" + (" (synthetic sample data)" if m["synthetic"] else "")
          + f", holdout accuracy {m['accuracy']}, AUC {m['auc']}")
    print(f"Database        : {database.DB_PATH}" + ("  (temporary storage, resets on restart)" if config.EPHEMERAL else ""))
    print(f"Demo logins     : {seed.DEMO_STUDENT_EMAIL} / {seed.DEMO_OFFICER_EMAIL}   password: {seed.DEMO_PASSWORD}")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)
