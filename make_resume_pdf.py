"""Generate a realistic resume PDF using reportlab."""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER

OUTPUT = "input/resume.pdf"

doc = SimpleDocTemplate(OUTPUT, pagesize=letter,
                        topMargin=0.6*inch, bottomMargin=0.6*inch,
                        leftMargin=0.75*inch, rightMargin=0.75*inch)

styles = getSampleStyleSheet()
story = []

# ── Custom styles ──────────────────────────────────────────────────────────
name_style = ParagraphStyle("Name", fontSize=20, fontName="Helvetica-Bold",
                             alignment=TA_CENTER, spaceAfter=4)
contact_style = ParagraphStyle("Contact", fontSize=10, fontName="Helvetica",
                                alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor("#444444"))
section_style = ParagraphStyle("Section", fontSize=12, fontName="Helvetica-Bold",
                                spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1a237e"),
                                borderPad=2)
body_style = ParagraphStyle("Body", fontSize=10, fontName="Helvetica",
                             spaceAfter=3, leading=14)
bullet_style = ParagraphStyle("Bullet", fontSize=10, fontName="Helvetica",
                               leftIndent=14, spaceAfter=2, bulletText="•")
job_title_style = ParagraphStyle("JobTitle", fontSize=11, fontName="Helvetica-Bold", spaceAfter=1)
job_meta_style = ParagraphStyle("JobMeta", fontSize=10, fontName="Helvetica-Oblique",
                                 textColor=colors.HexColor("#555555"), spaceAfter=3)

def section(title):
    story.append(Spacer(1, 6))
    story.append(Paragraph(title.upper(), section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a237e")))
    story.append(Spacer(1, 4))

# ── Header ─────────────────────────────────────────────────────────────────
story.append(Paragraph("Priya Sharma", name_style))
story.append(Paragraph("Senior Machine Learning Engineer", contact_style))
story.append(Paragraph(
    "priya.sharma@gmail.com  |  +91 98765 43210  |  Hyderabad, India",
    contact_style))
story.append(Paragraph(
    "linkedin.com/in/priya-sharma-ml  |  github.com/priyasharma-ml",
    contact_style))

# ── Summary ────────────────────────────────────────────────────────────────
section("Professional Summary")
story.append(Paragraph(
    "Machine Learning Engineer with 6+ years of experience building production-grade AI/ML systems. "
    "Specialist in NLP, deep learning, and MLOps with hands-on expertise deploying models on AWS and GCP. "
    "Led teams of 4–8 engineers and reduced model inference latency by 60% at TechCorp Solutions.",
    body_style))

# ── Skills ─────────────────────────────────────────────────────────────────
section("Skills")
skills_data = [
    ("Languages", "Python, SQL, Bash, R"),
    ("ML / AI", "TensorFlow, PyTorch, scikit-learn, Hugging Face, LangChain, RAG"),
    ("Data", "Pandas, NumPy, Spark, Airflow, dbt"),
    ("Cloud & DevOps", "AWS (SageMaker, EC2, S3), GCP, Docker, Kubernetes, CI/CD"),
    ("Databases", "PostgreSQL, MongoDB, Redis, Elasticsearch"),
    ("Frameworks", "FastAPI, Django, Flask"),
]
for category, items in skills_data:
    story.append(Paragraph(f"<b>{category}:</b> {items}", body_style))

# ── Experience ─────────────────────────────────────────────────────────────
section("Experience")

jobs = [
    {
        "title": "Senior Machine Learning Engineer",
        "company": "TechCorp Solutions",
        "location": "Hyderabad, India",
        "dates": "January 2021 – Present",
        "bullets": [
            "Architected and deployed a real-time recommendation engine serving 2M+ daily users.",
            "Built RAG pipeline using LangChain, FAISS and OpenAI GPT-4, reducing support tickets by 35%.",
            "Reduced model training time by 40% through distributed training on AWS SageMaker.",
            "Mentored 4 junior engineers and established ML code review standards.",
        ]
    },
    {
        "title": "Data Scientist",
        "company": "DataWave Analytics",
        "location": "Bengaluru, India",
        "dates": "June 2019 – December 2020",
        "bullets": [
            "Developed NLP sentiment analysis models on 10M+ customer reviews with 91% accuracy.",
            "Created automated ETL pipelines using Apache Airflow and dbt, saving 20 engineering hours/week.",
            "Presented model insights to C-suite, influencing Q3 product roadmap decisions.",
        ]
    },
    {
        "title": "Junior Data Analyst",
        "company": "DataWave Analytics",
        "location": "Bengaluru, India",
        "dates": "June 2018 – May 2019",
        "bullets": [
            "Performed EDA and data cleaning on large datasets using Python and pandas.",
            "Created executive dashboards in Tableau; reduced manual reporting effort by 15 hours/week.",
        ]
    },
]

for job in jobs:
    story.append(Paragraph(job["title"], job_title_style))
    story.append(Paragraph(f"{job['company']}  |  {job['location']}  |  {job['dates']}", job_meta_style))
    for b in job["bullets"]:
        story.append(Paragraph(b, bullet_style))
    story.append(Spacer(1, 6))

# ── Education ─────────────────────────────────────────────────────────────
section("Education")
story.append(Paragraph("M.Tech in Computer Science & Engineering", job_title_style))
story.append(Paragraph("Indian Institute of Technology Hyderabad  |  2016 – 2018  |  GPA: 8.7/10", job_meta_style))
story.append(Spacer(1, 4))
story.append(Paragraph("B.E. in Electronics & Communication Engineering", job_title_style))
story.append(Paragraph("Osmania University, Hyderabad  |  2012 – 2016  |  GPA: 9.1/10", job_meta_style))

# ── Projects ─────────────────────────────────────────────────────────────
section("Projects")
story.append(Paragraph("<b>CandidateIQ</b> — Open-source resume parsing library (GitHub: 850+ stars)", body_style))
story.append(Paragraph(
    "Built with Python, spaCy, and Pydantic. Extracts structured data from PDF resumes with 94% accuracy "
    "across 15 resume formats.", body_style))
story.append(Spacer(1, 4))
story.append(Paragraph("<b>MLOps Pipeline Template</b> — End-to-end ML training & serving on Kubernetes", body_style))
story.append(Paragraph(
    "Docker + Kubernetes + Prometheus + Grafana stack for reproducible ML experiments.", body_style))

doc.build(story)
print(f"✅ Resume PDF written to {OUTPUT}")
