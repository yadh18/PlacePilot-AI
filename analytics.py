"""Placement analytics for the officer dashboard, computed with pandas."""
from __future__ import annotations

from html import escape

import pandas as pd

DEPT_ORDER = ["CSE", "IT", "AI&DS", "ECE", "EEE", "MECH"]
STAGES = ["Applied", "Shortlisted", "Interview", "Offered"]
BANDS = [(0, 39), (40, 54), (55, 69), (70, 84), (85, 100)]


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def overview(data: dict, matches: dict, readiness: dict, demand: dict, today: str) -> dict:
    jobs = pd.DataFrame(data["jobs"], columns=["id", "companyId", "title", "ctc", "openings", "deadline"])
    jobs["open"] = jobs["deadline"] >= today
    apps = pd.DataFrame(data["applications"], columns=["id", "studentId", "jobId", "status"])
    placed_ids = set(apps.loc[apps["status"] == "Offered", "studentId"])
    students = pd.DataFrame([{"id": s["id"], "name": s["name"], "dept": s["dept"], "readiness": readiness[s["id"]]["score"],
                              "placed": s["id"] in placed_ids} for s in data["students"]],
                            columns=["id", "name", "dept", "readiness", "placed"])
    students["placed"] = students["placed"].astype(bool)
    students["readiness"] = students["readiness"].astype(float)
    pairs = pd.DataFrame([{"studentId": sid, "jobId": jid, "score": m["score"], "eligible": m["elig"]["ok"]}
                          for sid, per_job in matches.items() for jid, m in per_job.items()],
                         columns=["studentId", "jobId", "score", "eligible"])
    pairs["eligible"] = pairs["eligible"].astype(bool)
    pairs["score"] = pairs["score"].astype(float)
    company_name = {c["id"]: c["name"] for c in data["companies"]}
    n, n_placed = len(students), int(students["placed"].sum())
    offers = apps[apps["status"] == "Offered"].merge(jobs, left_on="jobId", right_on="id", suffixes=("", "_job"))

    # --- headline numbers ---
    tiles = {
        "students": n, "depts": int(students["dept"].nunique()), "companies": len(data["companies"]), "openJobs": int(jobs["open"].sum()),
        "applications": len(apps), "interview": int((apps["status"] == "Interview").sum()), "placed": n_placed,
        "placedPct": round(n_placed / n * 100) if n else 0, "offers": len(offers),
        "avgCtc": round(float(offers["ctc"].mean()), 1) if len(offers) else None,
    }

    # --- readiness distribution ---
    bins = pd.cut(students["readiness"], bins=[-1, 39, 54, 69, 84, 100], labels=False)
    counts = {int(k): int(v) for k, v in bins.value_counts().items()}
    bands = [{"a": a, "b": b, "n": int(counts.get(i, 0))} for i, (a, b) in enumerate(BANDS)]
    mean = round(float(students["readiness"].mean())) if n else 0

    # --- application funnel: how many applications reached each stage ---
    live = apps[apps["status"] != "Rejected"]
    stage_index = live["status"].map({s: i for i, s in enumerate(STAGES)})
    funnel = [{"st": s, "n": int((stage_index >= i).sum())} for i, s in enumerate(STAGES)]
    rejected = int((apps["status"] == "Rejected").sum())

    # --- placement by department ---
    by_dept = students.groupby("dept").agg(n=("id", "count"), placed=("placed", "sum"), readiness=("readiness", "mean"))
    order = [d for d in DEPT_ORDER if d in by_dept.index] + [d for d in by_dept.index if d not in DEPT_ORDER]
    depts = [{"dp": d, "n": int(by_dept.loc[d, "n"]), "placed": int(by_dept.loc[d, "placed"])} for d in order]

    # --- generated insights ---
    insights = []
    dm = pd.DataFrame(demand["list"], columns=["skill", "jobs", "must", "weight", "supply"])
    n_jobs, n_students = demand["nJobs"], max(1, demand["nStudents"])
    wide = dm[dm["jobs"] >= 2].copy()
    if len(wide) and n_jobs:
        wide["gap"] = wide["jobs"] / n_jobs - wide["supply"] / n_students
        g = wide.sort_values("gap", ascending=False).iloc[0]
        insights.append(["Largest skill gap",
                         f"<b>{escape(g['skill'])}</b> appears in {int(g['jobs'])} of {n_jobs} open roles, but only {int(g['supply'])} of "
                         f"{demand['nStudents']} students list it. A short workshop here would lift the most match scores."])
    open_jobs = jobs[jobs["open"]]
    if len(open_jobs):
        strong = pairs[pairs["eligible"] & (pairs["score"] >= 60)].groupby("jobId").size()
        fill = open_jobs.assign(strong=open_jobs["id"].map(strong).fillna(0).astype(int)).sort_values("strong", kind="stable")
        h = fill.iloc[0]
        insights.append(["Hardest role to fill",
                         f"<b>{escape(h['title'])}</b> at {escape(company_name.get(h['companyId'], 'Unknown company'))} has "
                         f"{_plural(int(h['strong']), 'eligible student')} scoring 60 or above for {_plural(int(h['openings']), 'opening')}."])
    risk = students[(~students["placed"]) & (students["readiness"] < 45)]
    if len(risk):
        names = ", ".join(escape(x) for x in risk["name"].head(3))
        insights.append(["Students needing support",
                         f"<b>{len(risk)} unplaced {'student has' if len(risk) == 1 else 'students have'}</b> a readiness score below 45, including {names}."])
    if len(by_dept) > 1:
        ranked = by_dept.sort_values("readiness")
        insights.append(["Readiness by department",
                         f"<b>{escape(ranked.index[0])}</b> has the lowest average readiness at {round(float(ranked['readiness'].iloc[0]))}. "
                         f"<b>{escape(ranked.index[-1])}</b> leads at {round(float(ranked['readiness'].iloc[-1]))}."])
    if len(pairs) and len(open_jobs):
        applied = set(zip(apps["studentId"], apps["jobId"]))
        cand = pairs[pairs["eligible"] & (pairs["score"] >= 70) & pairs["jobId"].isin(set(open_jobs["id"])) & ~pairs["studentId"].isin(placed_ids)]
        untapped = sum(1 for sid, jid in zip(cand["studentId"], cand["jobId"]) if (sid, jid) not in applied)
        if untapped:
            insights.append(["Untapped matches",
                             f"<b>{_plural(untapped, 'strong match', 'strong matches')}</b> (eligible, 70 or above) {'has' if untapped == 1 else 'have'} not turned into applications yet. "
                             "Use AI shortlisting to nudge those students."])

    return {"tiles": tiles, "demand": demand["list"][:10], "nJobs": demand["nJobs"], "nStudents": demand["nStudents"], "bands": bands, "mean": mean,
            "funnel": funnel, "rejected": rejected, "depts": depts, "insights": insights}
