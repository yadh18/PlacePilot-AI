# PlacePilot AI

AI-powered college placement management system. Students see how well they match each open
role, which skills they are missing and how learning a skill would change their scores.
Placement officers manage students, companies and job postings, get ranked shortlists and
see placement analytics.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

| Account | Email | Password |
| --- | --- | --- |
| Student demo | aarav@placepilot.demo | demo1234 |
| Placement officer demo | officer@placepilot.demo | demo1234 |

New students can register from the sign-in screen. The first start creates `data/placepilot.db`
with sample data and trains the readiness model. The first start with `sentence-transformers`
installed also downloads the `all-MiniLM-L6-v2` model (about 90 MB), so it needs internet once.

To use another port: `PORT=8000 python app.py` (Windows: `set PORT=8000` first).

## Technology

| Part | Used for |
| --- | --- |
| Flask | Web server, JSON API, session login |
| SQLite | All data: users, students, skills, projects, companies, jobs, applications |
| Sentence Transformers | Semantic similarity between a student's profile and a job description |
| scikit-learn | Logistic regression readiness model; TF-IDF fallback for semantic similarity |
| difflib | Fuzzy skill matching and spelling correction of typed skills |
| pandas | Placement analytics and generated insights |
| pypdf | Reading text out of uploaded PDF resumes |
| HTML, CSS, JavaScript | Single-page front end in `static/index.html` (hand-written CSS, no build step) |

## Project layout

```
app.py               Flask routes, login, input validation
ai_engine.py         Skill taxonomy, difflib matching, semantic similarity, match score,
                     eligibility, skill roadmap, What-If simulation, campus skill demand
readiness_model.py   scikit-learn readiness model: training, loading, prediction
analytics.py         pandas analytics for the officer dashboard
database.py          SQLite schema, sample-data seeding, queries
seed.py              Sample companies, roles, students and applications (all fictional)
static/index.html    Front end
data/                Created on first run: database, trained model, training CSV, session key
```

## How the scores work

**Match score (0 to 100)** = 55% skill coverage + 30% semantic similarity + 15% academic fit.
These weights are set in `WEIGHTS` in `ai_engine.py`.

- *Skill coverage.* Each required skill is compared with the student's skills. An exact match
  earns full credit. A near-identical spelling earns its `difflib` ratio (0.82 or higher).
  A closely related skill (Django for Flask, PyTorch for TensorFlow) earns partial credit from
  the `REL` table. Must-have skills carry full weight, optional skills 40%.
- *Semantic similarity.* The job text and the student's profile text (skills, projects,
  certificates, experience, resume) are embedded with the Sentence Transformer and compared by
  cosine similarity. The raw cosine is mapped linearly from the range in `Semantic.SCALE` onto
  0 to 1.
- *Academic fit.* CGPA against the cutoff, reduced for excess backlogs or a department that is
  not eligible.

**Eligibility** is a separate pass or fail check on CGPA, backlogs and department. Students can
only apply to roles they are eligible for.

**Skill roadmap.** Every skill the student is missing is added to the profile one at a time,
every role that asks for it is re-scored, and skills are ranked by total points gained.

**What-If Simulator.** `POST /api/simulate` re-scores every role with the chosen skills added,
without saving them. Saving the skills afterwards gives exactly the simulated scores.

**Readiness score.** A logistic regression predicts the probability of placement from seven
factors (role alignment, academics, skill depth, projects, experience, certifications, resume).
The score is that probability times 100.

## Things to know before you rely on it

- **The readiness model is trained on synthetic data.** There is no real placement history in
  this project, so `readiness_model.py` generates 1,500 made-up records on first run and trains
  on those. The scores show that the pipeline works; they are not evidence about real students.
  To use real records, replace `data/placement_history.csv` (the column format is documented at
  the top of `readiness_model.py`), delete `data/placement_history.SYNTHETIC`, and run
  `python readiness_model.py`.
- **Semantic fallback.** If `sentence-transformers` is not installed, or the model cannot be
  downloaded, the app uses scikit-learn TF-IDF instead and says so in the terminal, in the
  "How the match score is calculated" panel and under AI insights. Set
  `PLACEPILOT_SEMANTIC=tfidf` to force the fallback, or `PLACEPILOT_MODEL=<name or path>` to use
  a different model.
- **Semantic scaling for the transformer is a starting point.** `Semantic.SCALE["sbert"]` maps
  cosine 0.15 to 0 and 0.75 to 1. Check a few student and role pairs once the model is running
  and adjust those two numbers if scores look compressed or saturated.
- **Sample data.** The 24 students, 10 companies and 15 roles are fictional. The officer's
  "Reset sample data" button erases the database and restores them.
- **Development server.** `python app.py` uses Flask's built-in server, which is fine for a demo
  or a lab. For real use put it behind a production WSGI server and HTTPS.

## API

All routes return JSON. Routes other than login and register need a signed-in session.

| Method and path | Who | Purpose |
| --- | --- | --- |
| `GET /api/state` | anyone | Everything the page needs for the current user, with all scores |
| `POST /api/login`, `/api/register`, `/api/logout` | anyone | Session |
| `PUT /api/me/profile` | student | Personal and academic details |
| `POST /api/me/skills`, `/api/me/skills/remove` | student | Add (with spelling correction) or remove skills |
| `POST /api/me/items/<projects\|certs\|exp>`, `DELETE .../<id>` | student | Projects, certifications, experience |
| `POST /api/me/resume/extract` | student | Read text from an uploaded PDF or text file |
| `POST /api/me/resume`, `DELETE /api/me/resume` | student | Save or remove the resume text |
| `POST /api/simulate` | student | What-If Simulator |
| `POST /api/applications`, `DELETE /api/applications/<id>` | student | Apply, withdraw |
| `PUT /api/applications/<id>` | officer | Move an application to another stage |
| `POST /api/shortlist` | officer | Shortlist a student for a role |
| `POST/PUT/DELETE /api/students`, `/api/companies`, `/api/jobs` | officer | Manage records |
| `POST /api/extract-skills`, `/api/normalize` | signed in | Skill extraction and normalisation |
| `POST /api/reset` | officer | Restore the sample data |
