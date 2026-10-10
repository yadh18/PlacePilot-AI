"""SQLite storage for PlacePilot AI: schema, sample-data seeding and the queries the app needs."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

import seed
from ai_engine import normalize_skill, split_list

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "placepilot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    role          TEXT NOT NULL CHECK (role IN ('student', 'officer')),
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS students (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    dept        TEXT NOT NULL DEFAULT 'CSE',
    cgpa        REAL NOT NULL DEFAULT 0,
    backlogs    INTEGER NOT NULL DEFAULT 0,
    grad_year   INTEGER NOT NULL DEFAULT 2027,
    phone       TEXT NOT NULL DEFAULT '',
    tenth       TEXT NOT NULL DEFAULT '',
    twelfth     TEXT NOT NULL DEFAULT '',
    headline    TEXT NOT NULL DEFAULT '',
    resume_name TEXT,
    resume_text TEXT,
    resume_date TEXT
);
CREATE TABLE IF NOT EXISTS student_skills (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    skill      TEXT NOT NULL,
    UNIQUE (student_id, skill)
);
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tech        TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS certifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    issuer     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS experience (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    org         TEXT NOT NULL DEFAULT '',
    months      INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS companies (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    sector   TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    about    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'Full-time',
    ctc          REAL NOT NULL DEFAULT 0,
    pay          TEXT NOT NULL DEFAULT '',
    location     TEXT NOT NULL DEFAULT '',
    min_cgpa     REAL NOT NULL DEFAULT 0,
    max_backlogs INTEGER NOT NULL DEFAULT 0,
    depts        TEXT NOT NULL DEFAULT '[]',
    openings     INTEGER NOT NULL DEFAULT 1,
    deadline     TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS job_skills (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill  TEXT NOT NULL,
    must   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS applications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    job_id     INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'Applied',
    applied_on TEXT NOT NULL,
    updated_on TEXT NOT NULL,
    UNIQUE (student_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_skills_student ON student_skills(student_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_job ON job_skills(job_id);
CREATE INDEX IF NOT EXISTS idx_apps_student ON applications(student_id);
CREATE INDEX IF NOT EXISTS idx_apps_job ON applications(job_id);
"""
TABLES = ["applications", "job_skills", "jobs", "companies", "experience", "certifications", "projects", "student_skills", "students", "users"]


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False) -> None:
    """Create the tables, and load the sample data when the database is empty (or on reset)."""
    conn = connect()
    try:
        if reset:
            for t in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed_db(conn)
        conn.commit()
    finally:
        conn.close()


def seed_db(conn: sqlite3.Connection) -> None:
    pw = generate_password_hash(seed.DEMO_PASSWORD)
    company_ids = [conn.execute("INSERT INTO companies (name, sector, location, about) VALUES (?, ?, ?, ?)", c).lastrowid for c in seed.COMPANIES]
    job_ids = []
    for c, title, jtype, ctc, pay, loc, min_cgpa, max_back, depts, openings, days, desc, must, nice in seed.JOBS:
        jid = conn.execute(
            "INSERT INTO jobs (company_id, title, type, ctc, pay, location, min_cgpa, max_backlogs, depts, openings, deadline, description) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (company_ids[c - 1], title, jtype, ctc, pay, loc, min_cgpa, max_back, json.dumps(depts), openings, seed.iso_plus(days), desc)).lastrowid
        set_job_skills(conn, jid, must, nice)
        job_ids.append(jid)
    student_ids = []
    for i in range(len(seed.STUDENTS)):
        p = seed.student_profile(i)
        sid = create_student(conn, p["name"], p["email"], pw, p["dept"], p["cgpa"], p["backlogs"], p["grad_year"], hashed=True)
        conn.execute("UPDATE students SET tenth = ?, twelfth = ?, headline = ? WHERE user_id = ?", (p["tenth"], p["twelfth"], p["headline"], sid))
        set_student_skills(conn, sid, p["skills"])
        for pr in p["projects"]:
            conn.execute("INSERT INTO projects (student_id, title, description, tech) VALUES (?,?,?,?)", (sid, pr["title"], pr["desc"], json.dumps(pr["tech"])))
        for c in p["certs"]:
            conn.execute("INSERT INTO certifications (student_id, name, issuer) VALUES (?,?,?)", (sid, c["name"], c["issuer"]))
        for e in p["exp"]:
            conn.execute("INSERT INTO experience (student_id, role, org, months, description) VALUES (?,?,?,?,?)", (sid, e["role"], e["org"], e["months"], e["desc"]))
        student_ids.append(sid)
    for s, j, status, ago in seed.APPLICATIONS:
        conn.execute("INSERT INTO applications (student_id, job_id, status, applied_on, updated_on) VALUES (?,?,?,?,?)",
                     (student_ids[s], job_ids[j], status, seed.iso_plus(-ago), seed.iso_plus(-max(0, ago - 3))))
    name, email, title = seed.OFFICER
    conn.execute("INSERT INTO users (role, name, email, password_hash, title) VALUES ('officer', ?, ?, ?, ?)", (name, email, pw, title))


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def create_student(conn, name, email, password, dept, cgpa, backlogs=0, grad_year=2027, hashed=False) -> int:
    pw = password if hashed else generate_password_hash(password)
    uid = conn.execute("INSERT INTO users (role, name, email, password_hash) VALUES ('student', ?, ?, ?)", (name, email, pw)).lastrowid
    conn.execute("INSERT INTO students (user_id, dept, cgpa, backlogs, grad_year) VALUES (?,?,?,?,?)", (uid, dept, cgpa, backlogs, grad_year))
    return uid


def set_student_skills(conn, sid: int, names: list[str]) -> None:
    conn.execute("DELETE FROM student_skills WHERE student_id = ?", (sid,))
    conn.executemany("INSERT OR IGNORE INTO student_skills (student_id, skill) VALUES (?, ?)", [(sid, n) for n in names])


def add_student_skills(conn, sid: int, text) -> dict:
    """Normalise typed skills and add the new ones. Returns what was added and what was auto-corrected."""
    have = {r["skill"] for r in conn.execute("SELECT skill FROM student_skills WHERE student_id = ?", (sid,))}
    added, fixed = [], []
    for raw in (text if isinstance(text, list) else split_list(text)):
        n = normalize_skill(raw)
        if not n or n["name"] in have:
            continue
        conn.execute("INSERT INTO student_skills (student_id, skill) VALUES (?, ?)", (sid, n["name"]))
        have.add(n["name"])
        added.append(n["name"])
        if n["how"] == "fuzzy":
            fixed.append(f'"{n["raw"]}" as {n["name"]}')
    return {"added": added, "fixed": fixed}


def set_job_skills(conn, jid: int, must: list[str], nice: list[str]) -> None:
    conn.execute("DELETE FROM job_skills WHERE job_id = ?", (jid,))
    conn.executemany("INSERT INTO job_skills (job_id, skill, must) VALUES (?, ?, 1)", [(jid, k) for k in must])
    conn.executemany("INSERT INTO job_skills (job_id, skill, must) VALUES (?, ?, 0)", [(jid, k) for k in nice])


# ---------------------------------------------------------------------------
# Reads (shaped the way the front end and the AI engine expect them)
# ---------------------------------------------------------------------------
def _group(rows, key):
    out: dict[int, list] = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return out


def load_data(conn) -> dict:
    skills = _group(conn.execute("SELECT student_id, skill FROM student_skills ORDER BY id").fetchall(), "student_id")
    projects = _group(conn.execute("SELECT * FROM projects ORDER BY id").fetchall(), "student_id")
    certs = _group(conn.execute("SELECT * FROM certifications ORDER BY id").fetchall(), "student_id")
    exps = _group(conn.execute("SELECT * FROM experience ORDER BY id").fetchall(), "student_id")
    students = []
    for r in conn.execute("SELECT u.id, u.name, u.email, s.* FROM users u JOIN students s ON s.user_id = u.id ORDER BY u.id"):
        sid = r["id"]
        students.append({
            "id": str(sid), "name": r["name"], "email": r["email"], "dept": r["dept"], "cgpa": r["cgpa"], "backlogs": r["backlogs"],
            "gradYear": r["grad_year"], "phone": r["phone"], "tenth": r["tenth"], "twelfth": r["twelfth"], "headline": r["headline"],
            "skills": [x["skill"] for x in skills.get(sid, [])],
            "projects": [{"id": str(p["id"]), "title": p["title"], "desc": p["description"], "tech": json.loads(p["tech"] or "[]")} for p in projects.get(sid, [])],
            "certs": [{"id": str(c["id"]), "name": c["name"], "issuer": c["issuer"]} for c in certs.get(sid, [])],
            "exp": [{"id": str(e["id"]), "role": e["role"], "org": e["org"], "months": e["months"], "desc": e["description"]} for e in exps.get(sid, [])],
            "resume": {"name": r["resume_name"] or "Resume", "text": r["resume_text"], "date": r["resume_date"]} if r["resume_text"] else None,
        })
    job_skills = _group(conn.execute("SELECT job_id, skill, must FROM job_skills ORDER BY id").fetchall(), "job_id")
    jobs = []
    for r in conn.execute("SELECT * FROM jobs ORDER BY id"):
        ks = job_skills.get(r["id"], [])
        jobs.append({
            "id": str(r["id"]), "companyId": str(r["company_id"]), "title": r["title"], "type": r["type"], "ctc": r["ctc"], "pay": r["pay"],
            "location": r["location"], "minCgpa": r["min_cgpa"], "maxBacklogs": r["max_backlogs"], "depts": json.loads(r["depts"] or "[]"),
            "openings": r["openings"], "deadline": r["deadline"], "desc": r["description"],
            "must": [k["skill"] for k in ks if k["must"]], "nice": [k["skill"] for k in ks if not k["must"]],
        })
    companies = [{"id": str(r["id"]), "name": r["name"], "sector": r["sector"], "location": r["location"], "about": r["about"]}
                 for r in conn.execute("SELECT * FROM companies ORDER BY id")]
    applications = [{"id": str(r["id"]), "studentId": str(r["student_id"]), "jobId": str(r["job_id"]), "status": r["status"],
                     "date": r["applied_on"], "updated": r["updated_on"]} for r in conn.execute("SELECT * FROM applications ORDER BY id")]
    return {"students": students, "jobs": jobs, "companies": companies, "applications": applications}
