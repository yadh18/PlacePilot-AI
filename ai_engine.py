"""PlacePilot AI engine.

Skill taxonomy, difflib fuzzy matching, semantic similarity between student profiles and job
descriptions (Sentence Transformers, with a scikit-learn TF-IDF fallback), the match score,
eligibility checks, the skill roadmap and the What-If simulation.
"""
from __future__ import annotations

import difflib
import os
import re
import threading
from datetime import date
from functools import lru_cache

import numpy as np

# --------------------------------------------------------------------------------------
# Skill taxonomy: (canonical name, category, aliases, case-sensitive when read from text)
# --------------------------------------------------------------------------------------
SKILLS = [
    ("Python", "lang", ["py", "python3"]), ("Java", "lang", ["core java", "j2ee"]), ("C++", "lang", ["cpp", "c plus plus"]),
    ("C", "lang", ["c language", "c programming"], True), ("JavaScript", "lang", ["js", "es6", "ecmascript", "java script"]),
    ("TypeScript", "lang", ["type script"]), ("Kotlin", "lang", []),
    ("HTML", "web", ["html5"]), ("CSS", "web", ["css3"]), ("React", "web", ["reactjs", "react.js", "react js"]),
    ("Node.js", "web", ["nodejs", "node js", "expressjs", "express.js"]), ("Flask", "web", []), ("Django", "web", []),
    ("Spring Boot", "web", ["springboot", "spring framework"]),
    ("REST APIs", "web", ["rest api", "restful", "restful apis", "restful api", "api development", "web apis"]),
    ("Tailwind CSS", "web", ["tailwind", "tailwindcss"]), ("Android", "web", ["android development", "android studio"]),
    ("Flutter", "web", ["dart"]),
    ("SQL", "data", ["mysql", "postgresql", "postgres", "sqlite", "rdbms", "relational database", "relational databases"]),
    ("MongoDB", "data", ["mongo", "nosql"]), ("Pandas", "data", []), ("NumPy", "data", []),
    ("Data Analysis", "data", ["data analytics", "eda", "exploratory data analysis", "data cleaning"]),
    ("Statistics", "data", ["statistical analysis", "probability"]), ("Power BI", "data", ["powerbi"]), ("Tableau", "data", []),
    ("Excel", "data", ["ms excel", "microsoft excel", "spreadsheets"], True),
    ("Spark", "data", ["pyspark", "apache spark", "hadoop", "big data"], True),
    ("Machine Learning", "ml", ["ml", "supervised learning"]), ("Deep Learning", "ml", ["dl", "neural networks", "neural network"]),
    ("NLP", "ml", ["natural language processing", "text classification", "transformers", "language models"]),
    ("Computer Vision", "ml", ["opencv", "image processing"]), ("TensorFlow", "ml", ["keras"]), ("PyTorch", "ml", ["torch"]),
    ("Scikit-learn", "ml", ["sklearn", "scikit learn"]),
    ("AWS", "cloud", ["amazon web services", "ec2"]), ("Azure", "cloud", ["microsoft azure"]),
    ("Docker", "cloud", ["containers", "containerisation", "containerization", "containerised", "dockerised"]),
    ("Kubernetes", "cloud", ["k8s"]), ("CI/CD", "cloud", ["jenkins", "github actions", "ci cd", "continuous integration"]),
    ("Linux", "cloud", ["unix", "shell scripting", "bash"]),
    ("Data Structures", "core", ["dsa", "data structures and algorithms", "algorithms"]),
    ("OOP", "core", ["oops", "object oriented programming", "object-oriented programming", "object-oriented design"]),
    ("DBMS", "core", ["database management", "database management systems"]), ("Operating Systems", "core", ["os", "rtos"]),
    ("Computer Networks", "core", ["networking", "tcp/ip", "network protocols"]),
    ("Cybersecurity", "core", ["cyber security", "information security", "infosec", "network security", "penetration testing"]),
    ("Git", "tool", ["github", "gitlab", "version control"]),
    ("Testing", "tool", ["unit testing", "unit tests", "test automation", "qa", "quality assurance"]),
    ("Selenium", "tool", []), ("Figma", "tool", ["ui design", "ux design", "ui/ux"]), ("Agile", "tool", ["scrum"], True),
    ("Embedded C", "hw", ["embedded systems", "microcontrollers", "microcontroller", "firmware"]),
    ("VLSI", "hw", ["verilog", "vhdl", "rtl design"]), ("MATLAB", "hw", ["simulink"]),
    ("IoT", "hw", ["internet of things", "arduino", "raspberry pi", "mqtt"]), ("AutoCAD", "hw", ["solidworks", "cad"]),
    ("Communication", "soft", ["communication skills", "verbal communication", "presentation skills"]),
    ("Problem Solving", "soft", ["aptitude", "logical reasoning", "analytical thinking"]),
]

ALIAS: dict[str, str] = {}       # lowercase alias -> canonical name
SKILL_CAT: dict[str, str] = {}   # canonical name -> category
PATTERNS: list[tuple[re.Pattern, str]] = []


def _build_taxonomy() -> None:
    raw = []
    for entry in SKILLS:
        name, cat, aliases = entry[0], entry[1], entry[2]
        case_sensitive = len(entry) > 3 and entry[3]
        SKILL_CAT[name] = cat
        ALIAS[name.lower()] = name
        raw.append((name, name, case_sensitive))
        for a in aliases:
            ALIAS[a.lower()] = name
            raw.append((a, name, False))
    raw.sort(key=lambda r: -len(r[0]))            # longest first, so "Embedded C" wins over "C"
    for text, canon, case_sensitive in raw:
        pattern = r"(?<![A-Za-z0-9+#])" + re.escape(text) + r"(?![A-Za-z0-9+#])"
        PATTERNS.append((re.compile(pattern, 0 if case_sensitive else re.IGNORECASE), canon))


_build_taxonomy()
ALIAS_KEYS = list(ALIAS.keys())

# Related skills earn partial credit when the exact skill is missing.
_REL_PAIRS = [
    ("Flask", "Django", .5), ("Flask", "Spring Boot", .35), ("Django", "Spring Boot", .35), ("Node.js", "Flask", .35),
    ("Node.js", "Django", .35), ("Node.js", "Spring Boot", .35), ("TensorFlow", "PyTorch", .6), ("Power BI", "Tableau", .6),
    ("AWS", "Azure", .55), ("Java", "Kotlin", .5), ("Java", "C++", .3), ("C", "C++", .55), ("C", "Embedded C", .5),
    ("Android", "Flutter", .5), ("Machine Learning", "Deep Learning", .5), ("Machine Learning", "Scikit-learn", .6),
    ("Deep Learning", "PyTorch", .5), ("Deep Learning", "TensorFlow", .5), ("Pandas", "Data Analysis", .6),
    ("Pandas", "NumPy", .5), ("Excel", "Data Analysis", .35), ("Docker", "Kubernetes", .45), ("JavaScript", "TypeScript", .6),
    ("CSS", "Tailwind CSS", .5), ("SQL", "DBMS", .6), ("SQL", "MongoDB", .3), ("Testing", "Selenium", .55), ("Git", "CI/CD", .3),
    ("Linux", "Operating Systems", .4), ("Computer Networks", "Cybersecurity", .35), ("Statistics", "Data Analysis", .4),
    ("NLP", "Deep Learning", .35), ("React", "JavaScript", .3), ("MATLAB", "Python", .25),
]
REL: dict[tuple[str, str], float] = {}
for _a, _b, _w in _REL_PAIRS:
    REL[(_a, _b)] = _w
    REL[(_b, _a)] = _w

FUZZY_INPUT_CUTOFF = 0.80   # typed skill -> canonical skill ("Javascrpt" -> JavaScript)
FUZZY_MATCH_CUTOFF = 0.82   # required skill vs. a custom skill the student listed


@lru_cache(maxsize=50000)
def ratio(a: str, b: str) -> float:
    """difflib similarity ratio: 2 * matching characters / total characters."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def split_list(text) -> list[str]:
    return [x.strip() for x in re.split(r"[,;\n]", str(text or "")) if x.strip()]


def normalize_skill(raw) -> dict | None:
    """Turn whatever a user types into a canonical skill name."""
    raw = re.sub(r"\s+", " ", str(raw or "")).strip()[:60]
    if not raw:
        return None
    low = raw.lower()
    if low in ALIAS:
        return {"name": ALIAS[low], "how": "exact", "raw": raw}
    if len(low) >= 4:
        hit = difflib.get_close_matches(low, ALIAS_KEYS, n=1, cutoff=FUZZY_INPUT_CUTOFF)
        if hit:
            return {"name": ALIAS[hit[0]], "how": "fuzzy", "raw": raw}
    if len(raw) <= 3:
        name = raw.upper()
    elif any(c.isupper() for c in raw):
        name = raw
    else:
        name = re.sub(r"\b[a-z]", lambda m: m.group().upper(), raw)
    return {"name": name, "how": "custom", "raw": raw}


def normalize_list(text) -> list[str]:
    """Comma separated text -> de-duplicated canonical skill names, order preserved."""
    out: list[str] = []
    for item in split_list(text) if not isinstance(text, (list, tuple)) else text:
        n = normalize_skill(item)
        if n and n["name"] not in out:
            out.append(n["name"])
    return out


def extract_skills(text) -> list[str]:
    """Find every known skill mentioned in free text (a job description or a resume)."""
    t = " " + str(text or "") + " "
    found: list[str] = []
    for pattern, canon in PATTERNS:
        t2 = pattern.sub(" | ", t)
        if t2 != t:
            if canon not in found:
                found.append(canon)
            t = t2
    return found


# --------------------------------------------------------------------------------------
# Semantic similarity
# --------------------------------------------------------------------------------------
class Semantic:
    """Embeds text and compares it by cosine similarity.

    Primary backend: a pretrained Sentence Transformer (all-MiniLM-L6-v2 by default).
    Fallback: scikit-learn TF-IDF vectors fitted on the job descriptions, used when the
    sentence-transformers package or the model files are not available.

    Environment variables:
      PLACEPILOT_MODEL     model name or local path (default all-MiniLM-L6-v2)
      PLACEPILOT_SEMANTIC  "auto" (default), "sbert" or "tfidf"
    """

    # Raw cosine values are mapped linearly from [floor, ceiling] onto 0..1 before weighting.
    SCALE = {"sbert": (0.15, 0.75), "tfidf": (0.0, 0.55)}

    def __init__(self) -> None:
        self.model_name = os.environ.get("PLACEPILOT_MODEL", "all-MiniLM-L6-v2")
        self.mode = os.environ.get("PLACEPILOT_SEMANTIC", "auto").lower()
        self.kind = "tfidf"
        self.error = ""
        self._model = None
        self._loaded = False
        self._cache: dict[str, np.ndarray] = {}
        self._corpus_sig = None
        self._vectorizer = None
        self._lock = threading.RLock()

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if self.mode == "tfidf":
                self.error = "TF-IDF selected through PLACEPILOT_SEMANTIC"
                return
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self.kind = "sbert"
            except Exception as exc:  # package missing, no internet for the first download, etc.
                self.error = f"{type(exc).__name__}: {exc}"[:300]
                if self.mode == "sbert":
                    raise

    def info(self) -> dict:
        self.load()
        return {"kind": self.kind, "model": self.model_name if self.kind == "sbert" else "TF-IDF (scikit-learn)",
                "fallbackReason": self.error if self.kind == "tfidf" else ""}

    def set_corpus(self, job_texts: list[str]) -> None:
        """TF-IDF needs a vocabulary; it is refitted whenever the job postings change."""
        self.load()
        if self.kind != "tfidf":
            return
        sig = hash(tuple(job_texts))
        with self._lock:
            if sig == self._corpus_sig:
                return
            self._corpus_sig = sig
            self._cache.clear()
            self._vectorizer = None
            if any(t.strip() for t in job_texts):
                from sklearn.feature_extraction.text import TfidfVectorizer
                self._vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2),
                                                   token_pattern=r"[A-Za-z][A-Za-z0-9+#]*(?:\.[A-Za-z]+)?")
                self._vectorizer.fit([t for t in job_texts if t.strip()])

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalised vector per text (cached by text)."""
        self.load()
        with self._lock:
            missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
            if missing:
                if len(self._cache) > 6000:
                    self._cache.clear()
                if self.kind == "sbert":
                    vecs = self._model.encode(missing, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
                elif self._vectorizer is not None:
                    vecs = self._vectorizer.transform(missing).toarray()   # rows are already L2-normalised
                else:
                    vecs = np.zeros((len(missing), 1))
                for t, v in zip(missing, vecs):
                    self._cache[t] = np.asarray(v, dtype=np.float32)
            return np.vstack([self._cache[t] for t in texts]) if texts else np.zeros((0, 1), dtype=np.float32)

    def scale(self, cos: np.ndarray) -> np.ndarray:
        lo, hi = self.SCALE[self.kind]
        return np.clip((cos - lo) / (hi - lo), 0.0, 1.0)


# --------------------------------------------------------------------------------------
# Texts handed to the semantic model
# --------------------------------------------------------------------------------------
def job_text(job: dict, company: dict | None) -> str:
    parts = [job["title"] + ".", job["desc"]]
    if company and company.get("sector"):
        parts.append("Sector: " + company["sector"] + ".")
    if job["must"]:
        parts.append("Required skills: " + ", ".join(job["must"]) + ".")
    if job["nice"]:
        parts.append("Good to have: " + ", ".join(job["nice"]) + ".")
    return " ".join(parts)


def student_text(st: dict, extra=()) -> str:
    """Skills come first so they survive the model's input-length limit on long resumes."""
    skills = list(dict.fromkeys([*st["skills"], *extra]))
    parts = []
    if skills:
        parts.append("Skills: " + ", ".join(skills) + ".")
    if st.get("headline"):
        parts.append(st["headline"])
    for p in st["projects"]:
        parts.append(f"Project: {p['title']}. {p['desc']}" + (f" Built with {', '.join(p['tech'])}." if p["tech"] else ""))
    if st["certs"]:
        parts.append("Certifications: " + ", ".join(c["name"] for c in st["certs"]) + ".")
    for e in st["exp"]:
        parts.append(f"Experience: {e['role']} at {e['org']}. {e['desc']}")
    if st.get("resume"):
        parts.append(st["resume"]["text"][:6000])
    return " ".join(parts).strip()


# --------------------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------------------
WEIGHTS = {"cov": 0.55, "sem": 0.30, "ac": 0.15}   # skill coverage, semantic similarity, academic fit
NICE_WEIGHT = 0.4                                   # an optional skill counts 40% of a must-have


def credit(req: str, have: list[str]) -> tuple[float, str, str]:
    """How well the student's skills cover one required skill: (credit 0..1, how, via)."""
    if req in have:
        return 1.0, "match", ""
    best, via = 0.0, ""
    r = req.lower()
    for h in have:
        x = ratio(r, h.lower())
        if x > best:
            best, via = x, h
    if best >= FUZZY_MATCH_CUTOFF:
        return best, "fuzzy", via
    rel, rel_via = 0.0, ""
    for h in have:
        w = REL.get((req, h), 0.0)
        if w > rel:
            rel, rel_via = w, h
    if rel > 0:
        return rel, "related", rel_via
    return 0.0, "missing", ""


def eligibility(st: dict, job: dict) -> dict:
    cgpa, backlogs = float(st.get("cgpa") or 0), int(st.get("backlogs") or 0)
    in_dept = st.get("dept") in job["depts"]
    checks = [
        {"label": f"CGPA {cgpa:.2f} against a minimum of {float(job['minCgpa']):.1f}", "ok": cgpa >= float(job["minCgpa"])},
        {"label": f"{backlogs} active backlog{'' if backlogs == 1 else 's'}, limit {job['maxBacklogs']}", "ok": backlogs <= int(job["maxBacklogs"])},
        {"label": f"{st.get('dept')} is an eligible department" if in_dept else f"{st.get('dept')} is not in {', '.join(job['depts'])}", "ok": in_dept},
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def academic_fit(st: dict, job: dict) -> float:
    g, cutoff = float(st.get("cgpa") or 0), float(job["minCgpa"])
    a = 0.7 + 0.3 * min(1.0, max(0.0, (g - cutoff) / 1.5)) if g >= cutoff else max(0.0, min(1.0, 0.7 - (cutoff - g) * 0.5))
    if int(st.get("backlogs") or 0) > int(job["maxBacklogs"]):
        a *= 0.6
    if st.get("dept") not in job["depts"]:
        a *= 0.7
    return a


READINESS_BANDS = [(80, "Interview ready"), (65, "Placement ready"), (45, "Developing"), (0, "Needs foundation")]


class Engine:
    """Scores students against jobs for one snapshot of the database."""

    def __init__(self, data: dict, semantic: Semantic, readiness_model, today: str | None = None) -> None:
        self.students = data["students"]
        self.jobs = data["jobs"]
        self.companies = {c["id"]: c for c in data["companies"]}
        self.applications = data["applications"]
        self.semantic = semantic
        self.readiness_model = readiness_model
        self.today = today or date.today().isoformat()
        self.open_jobs = [j for j in self.jobs if j["deadline"] >= self.today]
        self.job_index = {j["id"]: i for i, j in enumerate(self.jobs)}
        texts = [job_text(j, self.companies.get(j["companyId"])) for j in self.jobs]
        semantic.set_corpus(texts)
        self.job_vecs = semantic.embed(texts)

    # ---- semantic similarity ----
    def similarities(self, texts: list[str]) -> np.ndarray:
        """Scaled similarity matrix: one row per text, one column per job."""
        if not self.jobs or not texts:
            return np.zeros((len(texts), len(self.jobs)))
        vecs = self.semantic.embed(texts)
        if vecs.shape[1] != self.job_vecs.shape[1]:
            return np.zeros((len(texts), len(self.jobs)))
        sims = self.semantic.scale(vecs @ self.job_vecs.T)
        for i, t in enumerate(texts):
            if not t:
                sims[i, :] = 0.0
        return sims

    # ---- one student against one job ----
    def _match(self, st: dict, job: dict, sem: float, extra=()) -> dict:
        have = list(dict.fromkeys([*st["skills"], *extra]))
        rows, total_w, got = [], 0.0, 0.0
        for skill, must in [*[(k, True) for k in job["must"]], *[(k, False) for k in job["nice"]]]:
            w = 1.0 if must else NICE_WEIGHT
            c, how, via = credit(skill, have)
            rows.append({"skill": skill, "w": w, "must": must, "c": round(c, 4), "how": how, "via": via})
            total_w += w
            got += w * c
        cov = got / total_w if total_w else 0.0
        ac = academic_fit(st, job)
        score = round(100 * (WEIGHTS["cov"] * cov + WEIGHTS["sem"] * sem + WEIGHTS["ac"] * ac))
        return {"jobId": job["id"], "score": int(score), "cov": round(cov, 4), "sem": round(float(sem), 4), "ac": round(ac, 4),
                "rows": rows, "elig": eligibility(st, job)}

    def match_all(self, st: dict, extra=(), sem_row=None) -> dict:
        if sem_row is None:
            sem_row = self.similarities([student_text(st, extra)])[0] if self.jobs else []
        return {j["id"]: self._match(st, j, float(sem_row[i]), extra) for i, j in enumerate(self.jobs)}

    def match_many(self, students: list[dict]) -> dict:
        sims = self.similarities([student_text(s) for s in students])
        return {s["id"]: self.match_all(s, sem_row=sims[i]) for i, s in enumerate(students)}

    # ---- readiness ----
    def readiness_parts(self, st: dict, matches: dict, extra=()) -> tuple[dict, int]:
        ranked = [matches[j["id"]] for j in self.open_jobs]
        pool = [m for m in ranked if m["elig"]["ok"]]
        top = sorted(pool or ranked, key=lambda m: -m["score"])[:3]
        avg = sum(m["score"] for m in top) / len(top) / 100 if top else 0.0
        n_skills = len(set([*st["skills"], *extra]))
        n_exp = len(st["exp"])
        clamp = lambda x: max(0.0, min(1.0, x))
        parts = {
            "market": avg * (1.0 if pool else 0.8),
            "acad": clamp(clamp((float(st.get("cgpa") or 0) - 5) / 4) - 0.1 * int(st.get("backlogs") or 0)),
            "skills": clamp(n_skills / 10),
            "proj": clamp(len(st["projects"]) / 3),
            "exp": 1.0 if n_exp >= 2 else 0.8 if n_exp == 1 else 0.0,
            "cert": clamp(len(st["certs"]) / 2),
            "resume": 1.0 if st.get("resume") else 0.0,
        }
        return parts, len(pool)

    def readiness(self, st: dict, matches: dict, extra=()) -> dict:
        parts, eligible = self.readiness_parts(st, matches, extra)
        score = int(round(100 * self.readiness_model.predict(parts)))
        label = next(lbl for cut, lbl in READINESS_BANDS if score >= cut)
        return {"score": score, "parts": {k: round(v, 4) for k, v in parts.items()}, "label": label, "eligible": eligible}

    # ---- skill-gap roadmap ----
    def roadmap(self, st: dict, matches: dict) -> list[dict]:
        """Add each missing skill on its own, re-score every role that asks for it, rank by total gain."""
        ranked = [matches[j["id"]] for j in self.open_jobs]
        pool = [m for m in ranked if m["elig"]["ok"]] or ranked
        jobs_by_id = {j["id"]: j for j in self.jobs}
        cand: dict[str, dict] = {}
        for m in pool:
            for r in m["rows"]:
                if r["c"] < 1:
                    e = cand.setdefault(r["skill"], {"jobs": [], "must": 0})
                    e["jobs"].append(jobs_by_id[m["jobId"]])
                    e["must"] += 1 if r["must"] else 0
        if not cand:
            return []
        skills = list(cand)
        sims = self.similarities([student_text(st, [k]) for k in skills])
        out = []
        for i, k in enumerate(skills):
            gains = [self._match(st, j, float(sims[i][self.job_index[j["id"]]]), [k])["score"] - matches[j["id"]]["score"] for j in cand[k]["jobs"]]
            total = sum(gains)
            if total > 0:
                out.append({"skill": k, "count": len(gains), "must": cand[k]["must"], "total": total,
                            "avg": round(total / len(gains), 2), "best": max(gains), "titles": [j["title"] for j in cand[k]["jobs"]]})
        out.sort(key=lambda e: (-e["total"], -e["count"]))
        return out

    # ---- what-if ----
    def simulate(self, st: dict, extra: list[str]) -> dict:
        matches = self.match_all(st, extra)
        return {"matches": matches, "readiness": self.readiness(st, matches, extra)}

    # ---- campus skill demand ----
    def demand(self) -> dict:
        d: dict[str, dict] = {}
        for j in self.open_jobs:
            for k in j["must"]:
                e = d.setdefault(k, {"skill": k, "jobs": 0, "must": 0})
                e["jobs"] += 1
                e["must"] += 1
            for k in j["nice"]:
                d.setdefault(k, {"skill": k, "jobs": 0, "must": 0})["jobs"] += 1
        rows = []
        for e in d.values():
            rows.append({**e, "weight": round(e["must"] + (e["jobs"] - e["must"]) * NICE_WEIGHT, 2),
                         "supply": sum(1 for s in self.students if e["skill"] in s["skills"])})
        rows.sort(key=lambda e: (-e["weight"], e["skill"]))
        return {"list": rows, "nJobs": len(self.open_jobs), "nStudents": len(self.students)}
