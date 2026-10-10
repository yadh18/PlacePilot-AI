"""Sample data for PlacePilot AI. Every student, company and role here is fictional."""
from __future__ import annotations

import re
from datetime import date, timedelta

DEMO_PASSWORD = "demo1234"
DEMO_STUDENT_EMAIL = "aarav@placepilot.demo"
DEMO_OFFICER_EMAIL = "officer@placepilot.demo"


def iso_plus(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


COMPANIES = [
    ("Kaveri Labs", "Product software", "Chennai", "Builds workflow software for mid-size manufacturers across South India."),
    ("Meridian Fintech", "Fintech", "Bengaluru", "Payments and lending infrastructure for small businesses."),
    ("Halcyon Cloud", "Cloud infrastructure", "Hyderabad", "Managed cloud hosting and reliability engineering services."),
    ("Tessera Analytics", "Data & analytics", "Pune", "Analytics and forecasting products for retail chains."),
    ("Orbitline Mobility", "EV & mobility", "Chennai", "Electric two-wheeler platforms and connected vehicle software."),
    ("Quanta Forge AI", "Applied AI", "Bengaluru", "Language technology for Indian regional languages."),
    ("Sapphire Semiconductors", "Chip design", "Bengaluru", "Mixed-signal chip design services."),
    ("BlueKite Commerce", "E-commerce", "Gurugram", "Marketplace platform for independent home-goods brands."),
    ("Lumen Shield Security", "Cybersecurity", "Hyderabad", "Security monitoring and incident response for banks."),
    ("Indus Grid Energy", "Energy tech", "Coimbatore", "Smart-grid hardware and substation automation."),
]

# (company number, title, type, annual value in LPA, package as shown, location, min CGPA, backlogs allowed,
#  eligible departments, openings, days until the deadline, description, must-have skills, good-to-have skills)
JOBS = [
    (1, "Software Development Engineer", "Full-time", 12, "₹12 LPA", "Chennai", 7.5, 0, ["CSE", "IT", "AI&DS"], 6, 18,
     "Design and build backend services for our workflow platform. You will write clean object-oriented Java, model relational data, review code through Git and reason carefully about data structures and algorithms. Exposure to Spring Boot services, containers and RESTful API design is a plus.",
     ["Data Structures", "Java", "SQL", "OOP", "Git"], ["Spring Boot", "Docker", "REST APIs"]),
    (1, "Frontend Engineer", "Full-time", 9, "₹9 LPA", "Chennai", 7, 0, ["CSE", "IT", "AI&DS"], 4, 21,
     "Build responsive, accessible interfaces in React for our customer dashboards. Strong JavaScript, semantic HTML and modern CSS are expected, along with comfortable use of Git. TypeScript, Tailwind CSS and Figma hand-off experience help.",
     ["JavaScript", "React", "HTML", "CSS", "Git"], ["TypeScript", "Tailwind CSS", "Figma"]),
    (2, "Backend Engineer (Python)", "Full-time", 10.5, "₹10.5 LPA", "Bengaluru", 7.5, 0, ["CSE", "IT", "AI&DS"], 5, 14,
     "Develop payment and ledger services in Python with Flask. You will design REST APIs, write SQL for relational databases, cover your code with unit tests and collaborate through Git. Experience with Docker and AWS deployment is welcome.",
     ["Python", "Flask", "SQL", "REST APIs", "Git"], ["Docker", "AWS", "Testing"]),
    (2, "Data Analyst", "Full-time", 7.5, "₹7.5 LPA", "Bengaluru", 7, 0, ["CSE", "IT", "AI&DS", "ECE"], 4, 25,
     "Turn transaction data into decisions. You will query with SQL, clean and explore data in Python, apply statistics to test hypotheses and present findings in Excel and Power BI dashboards. Tableau and Pandas experience is useful.",
     ["SQL", "Excel", "Python", "Data Analysis", "Statistics"], ["Power BI", "Tableau", "Pandas"]),
    (3, "Cloud & DevOps Associate", "Full-time", 8.5, "₹8.5 LPA", "Hyderabad", 6.5, 1, ["CSE", "IT", "ECE", "AI&DS"], 5, 12,
     "Operate and automate customer workloads on AWS. Daily work includes Linux administration, Docker containers, networking fundamentals and Git-based workflows. Knowledge of Kubernetes, CI/CD pipelines and Python scripting is an advantage.",
     ["Linux", "AWS", "Docker", "Git", "Computer Networks"], ["Kubernetes", "CI/CD", "Python"]),
    (4, "Machine Learning Engineer", "Full-time", 14, "₹14 LPA", "Pune", 8, 0, ["CSE", "IT", "AI&DS"], 3, 16,
     "Build demand forecasting models end to end. You will prepare data with Pandas, train and evaluate machine learning models in Python with scikit-learn, and apply statistics to validate results. Deep learning with PyTorch, NLP and SQL are valued.",
     ["Python", "Machine Learning", "Scikit-learn", "Pandas", "Statistics"], ["Deep Learning", "PyTorch", "NLP", "SQL"]),
    (4, "Business Intelligence Intern", "Internship", 4.2, "₹35,000 / month", "Pune", 6.5, 1, ["CSE", "IT", "AI&DS", "ECE", "EEE", "MECH"], 6, 10,
     "Six-month internship building reports for retail clients. You will write SQL, build Power BI dashboards, maintain Excel models and carry out data analysis for weekly reviews. Tableau, Python and clear communication are helpful.",
     ["SQL", "Power BI", "Excel", "Data Analysis"], ["Tableau", "Python", "Communication"]),
    (5, "Embedded Software Engineer", "Full-time", 8, "₹8 LPA", "Chennai", 7, 0, ["ECE", "EEE", "CSE"], 4, 20,
     "Write firmware for battery management and motor control units. Strong Embedded C and C, IoT connectivity and operating systems concepts such as scheduling are required. MATLAB modelling, Python test scripts and C++ are a bonus.",
     ["Embedded C", "C", "IoT", "Operating Systems"], ["MATLAB", "Python", "C++"]),
    (5, "Android Developer", "Full-time", 9, "₹9 LPA", "Chennai", 7, 0, ["CSE", "IT", "AI&DS"], 3, 23,
     "Build the rider companion app in Kotlin on Android. You will integrate REST APIs, manage releases through Git and write maintainable screens. Java, Flutter and automated testing experience are useful.",
     ["Kotlin", "Android", "REST APIs", "Git"], ["Java", "Flutter", "Testing"]),
    (6, "NLP Research Engineer", "Full-time", 16, "₹16 LPA", "Bengaluru", 8.5, 0, ["CSE", "AI&DS"], 2, 15,
     "Research and ship language models for Tamil, Telugu and Hindi. You need strong Python, natural language processing, deep learning with PyTorch and solid machine learning fundamentals. TensorFlow, Docker and statistics help.",
     ["Python", "NLP", "Deep Learning", "PyTorch", "Machine Learning"], ["TensorFlow", "Docker", "Statistics"]),
    (7, "VLSI Design Trainee", "Full-time", 7.2, "₹7.2 LPA", "Bengaluru", 7, 0, ["ECE", "EEE"], 5, 19,
     "Join the RTL design team. You will write and verify Verilog, script in C and model blocks in MATLAB. Python scripting, embedded systems exposure and Linux comfort are preferred.",
     ["VLSI", "C", "MATLAB"], ["Python", "Embedded C", "Linux"]),
    (8, "Full Stack Developer", "Full-time", 11, "₹11 LPA", "Gurugram", 7, 0, ["CSE", "IT", "AI&DS"], 4, 17,
     "Own features across our marketplace. The stack is React and JavaScript on the front end with Node.js, MongoDB and REST APIs behind it. TypeScript, Docker, AWS and SQL experience are a plus.",
     ["JavaScript", "React", "Node.js", "MongoDB", "REST APIs"], ["TypeScript", "Docker", "AWS", "SQL"]),
    (9, "Security Analyst", "Full-time", 8, "₹8 LPA", "Hyderabad", 7, 0, ["CSE", "IT", "ECE"], 3, 13,
     "Monitor and investigate security events for banking clients. You need cybersecurity fundamentals, computer networks, Linux and Python scripting. Operating systems internals, AWS and testing experience help.",
     ["Cybersecurity", "Computer Networks", "Linux", "Python"], ["Operating Systems", "AWS", "Testing"]),
    (10, "Graduate Engineer Trainee", "Full-time", 6, "₹6 LPA", "Coimbatore", 6.5, 2, ["EEE", "MECH", "ECE"], 8, 28,
     "Rotate through design, testing and field commissioning of substation equipment. MATLAB modelling, AutoCAD drawings, problem solving and clear communication are essential. Python, IoT and Excel are useful.",
     ["MATLAB", "AutoCAD", "Problem Solving", "Communication"], ["Python", "IoT", "Excel"]),
    (8, "QA Automation Engineer", "Full-time", 6.8, "₹6.8 LPA", "Gurugram", 6.5, 1, ["CSE", "IT", "ECE", "AI&DS"], 4, 22,
     "Automate regression testing for checkout and seller tools. You will write Selenium tests in Java, validate data with SQL and own test plans. CI/CD, Python and Agile experience are welcome.",
     ["Testing", "Selenium", "Java", "SQL"], ["CI/CD", "Python", "Agile"]),
]

PROJECTS = {
    "web": [("Campus Event Portal", "Responsive event registration site with a React front end, REST APIs and role-based login for club coordinators.", ["React", "JavaScript", "Node.js"]),
            ("Portfolio Site Generator", "Static site generator that turns a JSON profile into a themed portfolio using HTML and CSS templates.", ["HTML", "CSS", "JavaScript"])],
    "ml": [("Student Attrition Risk Model", "Trained and compared classification models with scikit-learn and pandas on anonymised academic records, with feature importance reporting.", ["Python", "Scikit-learn", "Pandas"]),
           ("Tamil News Topic Classifier", "Fine-tuned a transformer for text classification and served predictions through a small API.", ["Python", "NLP", "PyTorch"])],
    "data": [("Retail Sales Dashboard", "Cleaned three years of sales data with SQL and built an interactive Power BI dashboard for regional trends.", ["SQL", "Power BI", "Excel"]),
             ("Hostel Mess Feedback Analysis", "Survey data analysis in Python with statistics on satisfaction drivers.", ["Python", "Data Analysis", "Statistics"])],
    "backend": [("Library Management API", "REST API with authentication, fines and reservations backed by a relational database and unit tests.", ["SQL", "REST APIs", "Git"]),
                ("Expense Splitter", "Console and web app that settles shared expenses using graph algorithms.", ["Data Structures", "Java"])],
    "embedded": [("Smart Energy Meter", "Microcontroller-based meter that logs consumption over MQTT and raises tamper alerts.", ["Embedded C", "IoT"]),
                 ("Line Follower with PID", "Tuned a PID controller for a line-following robot and logged telemetry.", ["C", "MATLAB"])],
    "mobile": [("Campus Bus Tracker", "Android app showing live bus locations with offline timetable caching.", ["Kotlin", "Android"])],
    "security": [("Network Intrusion Monitor", "Packet capture and rule-based alerting for a lab network, with a weekly report of suspicious hosts.", ["Linux", "Computer Networks", "Python"])],
    "devops": [("Containerised Deploy Pipeline", "Dockerised a web service and automated build, test and deploy to AWS through a CI/CD pipeline.", ["Docker", "CI/CD", "AWS"]),
               ("Lab Server Monitoring", "Shell scripts and dashboards tracking uptime of department Linux servers.", ["Linux", "Python"])],
    "mech": [("Two-Stage Gearbox Design", "Designed and dimensioned a reduction gearbox in AutoCAD with load calculations validated in MATLAB.", ["AutoCAD", "MATLAB"])],
    "vlsi": [("8-bit ALU in Verilog", "Designed, simulated and synthesised an 8-bit ALU with timing analysis.", ["VLSI"])],
    "qa": [("Automated Regression Suite", "Selenium test suite covering checkout flows, run nightly with reports.", ["Selenium", "Testing", "Java"])],
}
CERTS = {"web": "Modern Web Development", "ml": "Machine Learning Foundations", "data": "Data Analytics with SQL", "backend": "Programming in Java",
         "embedded": "Embedded Systems Design", "mobile": "Android App Development", "security": "Ethical Hacking Basics",
         "devops": "Cloud Computing Fundamentals", "mech": "CAD for Engineers", "vlsi": "Digital VLSI Design", "qa": "Software Testing"}
ROLES = {"web": "Web Development Intern", "ml": "ML Research Intern", "data": "Data Analyst Intern", "backend": "Software Engineering Intern",
         "embedded": "Firmware Intern", "mobile": "Android Intern", "security": "SOC Intern", "devops": "Cloud Operations Intern",
         "mech": "Design Intern", "vlsi": "RTL Design Intern", "qa": "QA Intern"}
ORGS = ["Northbay Software", "Pallavi Systems", "Cauvery Digital", "Tidewater Tech", "Arkadia Works", "Seventh Mile Labs"]

# (name, department, CGPA, backlogs, skills, track, projects, certifications, internships)
STUDENTS = [
    ("Aarav Krishnan", "CSE", 8.1, 0, ["Python", "Java", "SQL", "HTML", "CSS", "JavaScript", "Git", "Data Structures", "OOP"], "backend", 2, 1, 0),
    ("Diya Venkatesh", "CSE", 9.1, 0, ["Python", "Machine Learning", "Scikit-learn", "Pandas", "NumPy", "Statistics", "SQL", "Deep Learning", "PyTorch", "Git"], "ml", 2, 2, 1),
    ("Karthik Subramanian", "IT", 7.4, 0, ["JavaScript", "React", "HTML", "CSS", "Node.js", "MongoDB", "Git", "REST APIs"], "web", 2, 1, 1),
    ("Meera Iyer", "AI&DS", 8.7, 0, ["Python", "NLP", "Deep Learning", "TensorFlow", "Machine Learning", "Pandas", "SQL"], "ml", 2, 2, 1),
    ("Rohan Pillai", "CSE", 6.8, 1, ["Java", "SQL", "HTML", "CSS", "Data Structures"], "backend", 1, 0, 0),
    ("Sneha Rajan", "ECE", 8.0, 0, ["Embedded C", "C", "IoT", "MATLAB", "Python", "Operating Systems"], "embedded", 2, 1, 1),
    ("Vignesh Kumar", "CSE", 7.9, 0, ["Linux", "AWS", "Docker", "Git", "Python", "Computer Networks", "CI/CD"], "devops", 2, 2, 1),
    ("Priya Natarajan", "IT", 8.4, 0, ["SQL", "Excel", "Python", "Data Analysis", "Power BI", "Statistics", "Tableau"], "data", 2, 1, 1),
    ("Arjun Menon", "CSE", 7.2, 0, ["Kotlin", "Android", "Java", "Git", "REST APIs"], "mobile", 1, 0, 1),
    ("Lakshmi Suresh", "AI&DS", 7.6, 0, ["Python", "Pandas", "SQL", "Data Analysis", "Excel", "Machine Learning"], "data", 2, 1, 0),
    ("Harish Balaji", "ECE", 6.9, 2, ["C", "MATLAB", "VLSI"], "vlsi", 1, 0, 0),
    ("Nivetha Ramesh", "CSE", 8.8, 0, ["Java", "Data Structures", "OOP", "SQL", "Spring Boot", "Git", "Docker", "REST APIs"], "backend", 2, 2, 1),
    ("Sanjay Mohan", "MECH", 7.1, 0, ["AutoCAD", "MATLAB", "Problem Solving", "Communication", "Excel"], "mech", 1, 1, 1),
    ("Keerthana Devi", "IT", 7.8, 0, ["Cybersecurity", "Computer Networks", "Linux", "Python", "Operating Systems"], "security", 1, 1, 0),
    ("Ashwin Raj", "CSE", 6.2, 3, ["HTML", "CSS", "JavaScript"], "web", 1, 0, 0),
    ("Fathima Noor", "CSE", 8.3, 0, ["JavaScript", "TypeScript", "React", "HTML", "CSS", "Tailwind CSS", "Figma", "Git"], "web", 2, 1, 1),
    ("Gokul Anand", "EEE", 7.5, 0, ["MATLAB", "Embedded C", "IoT", "C", "Python"], "embedded", 1, 0, 1),
    ("Ishaan Varma", "AI&DS", 9.3, 0, ["Python", "Deep Learning", "PyTorch", "NLP", "Machine Learning", "Statistics", "Docker", "TensorFlow"], "ml", 2, 2, 2),
    ("Janani Sekar", "CSE", 7.0, 1, ["Testing", "Selenium", "Java", "SQL", "Agile"], "qa", 1, 1, 0),
    ("Manoj Prabhu", "IT", 6.6, 0, ["Python", "Flask", "SQL", "HTML"], "backend", 1, 0, 0),
    ("Nandini Rao", "ECE", 8.5, 0, ["VLSI", "C", "MATLAB", "Python", "Linux", "Embedded C"], "vlsi", 1, 1, 1),
    ("Pranav Shankar", "CSE", 7.7, 0, ["Python", "Flask", "SQL", "REST APIs", "Git", "Docker", "Testing"], "backend", 1, 1, 1),
    ("Revathi Mani", "EEE", 6.4, 1, ["MATLAB", "Excel", "Communication"], "mech", 0, 0, 0),
    ("Tarun Elango", "MECH", 6.9, 0, ["AutoCAD", "Communication", "Problem Solving"], "mech", 1, 0, 0),
]

# (student index, job index, status, days since applying)
APPLICATIONS = [
    (0, 0, "Shortlisted", 9), (0, 2, "Applied", 3), (1, 5, "Offered", 20), (2, 11, "Interview", 12), (2, 1, "Applied", 4),
    (3, 9, "Interview", 11), (3, 5, "Shortlisted", 8), (5, 7, "Offered", 19), (6, 4, "Offered", 22), (7, 3, "Shortlisted", 7),
    (7, 6, "Applied", 2), (8, 8, "Interview", 10), (9, 3, "Applied", 5), (9, 6, "Shortlisted", 6), (11, 0, "Offered", 21),
    (12, 13, "Shortlisted", 6), (13, 12, "Interview", 9), (15, 1, "Offered", 18), (16, 7, "Applied", 4), (16, 13, "Applied", 3),
    (17, 9, "Offered", 17), (18, 14, "Shortlisted", 7), (19, 2, "Rejected", 13), (20, 10, "Interview", 8), (21, 2, "Shortlisted", 6),
    (4, 14, "Applied", 2), (14, 1, "Rejected", 12),
]

OFFICER = ("Prof. Malini Sundar", DEMO_OFFICER_EMAIL, "Placement Officer")


def student_email(index: int, name: str) -> str:
    return DEMO_STUDENT_EMAIL if index == 0 else re.sub(r"[^a-z]+", ".", name.lower()) + "@campus.example"


def student_profile(index: int) -> dict:
    """Expand one STUDENTS row into a full profile."""
    name, dept, cgpa, backlogs, skills, track, n_proj, n_cert, n_exp = STUDENTS[index]
    return {
        "name": name, "email": student_email(index, name), "dept": dept, "cgpa": cgpa, "backlogs": backlogs, "grad_year": 2027,
        "tenth": str(round(78 + (cgpa - 6) * 5 + index % 4)), "twelfth": str(round(74 + (cgpa - 6) * 6 + index % 3)),
        "headline": f"Final-year {dept} student interested in {ROLES[track].replace(' Intern', '').lower()} roles.",
        "skills": list(skills),
        "projects": [{"title": t, "desc": d, "tech": list(tech)} for t, d, tech in PROJECTS.get(track, [])[:n_proj]],
        "certs": [{"name": CERTS[track] if k == 0 else "Problem Solving through Programming",
                   "issuer": "NPTEL" if k == 0 else "Department value-added course"} for k in range(n_cert)],
        "exp": [{"role": ROLES[track], "org": ORGS[(index + k) % len(ORGS)], "months": 2 if k == 0 else 3,
                 "desc": f"Worked with the {track} team on production tasks and presented a final report."} for k in range(n_exp)],
    }
