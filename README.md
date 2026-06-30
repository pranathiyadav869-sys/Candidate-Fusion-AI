# 🚀 CandidateFusion AI – Multi-Source Candidate Data Transformation Pipeline 💼✨

<p align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-red?style=for-the-badge)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-PDF%20Parser-orange?style=for-the-badge)
![GitHub API](https://img.shields.io/badge/GitHub-REST%20API-black?style=for-the-badge&logo=github)
![JSON](https://img.shields.io/badge/JSON-Configuration-green?style=for-the-badge)
![CLI](https://img.shields.io/badge/Interface-CLI-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=for-the-badge)

</p>

---

# 🌍 Overview

CandidateFusion AI is a production-ready candidate data transformation pipeline designed to consolidate candidate information from multiple structured and unstructured sources into a single canonical profile.

Modern recruitment platforms receive candidate information from various systems including recruiter exports, ATS platforms, resumes, GitHub profiles, and other external sources. These records often contain duplicated, inconsistent, incomplete, or conflicting information.

CandidateFusion intelligently extracts, normalizes, validates, merges, and scores candidate data while maintaining complete provenance for every field. The final output is a configurable JSON profile suitable for downstream recruitment systems and analytics platforms.

---

# 🎯 Problem Statement

Recruitment platforms collect candidate data from multiple independent systems.

These datasets often suffer from:

- Duplicate candidate profiles
- Missing information
- Conflicting field values
- Different naming conventions
- Multiple date formats
- Invalid contact information
- Inconsistent skill names
- Lack of traceability

The objective of CandidateFusion AI is to build a deterministic, explainable, and production-ready data transformation engine capable of generating one trusted candidate profile from many heterogeneous data sources.

---

# ✨ Key Features

✅ Multi-source Candidate Ingestion

✅ Recruiter CSV Parser

✅ ATS JSON Parser

✅ Resume PDF Parser (PyMuPDF)

✅ GitHub REST API Integration

✅ Canonical Candidate Schema

✅ Intelligent Merge Engine

✅ Data Normalization Engine

✅ Confidence Scoring

✅ Provenance Tracking

✅ Configurable Output Projection

✅ Schema Validation using Pydantic

✅ Structured Logging

✅ Command Line Interface (CLI)

---

# 🏗️ System Architecture

```text
                 Recruiter CSV
                        │
                        ▼
                 ATS JSON Export
                        │
                        ▼
                 Resume PDF Parser
                        │
                        ▼
                 GitHub REST API
                        │
────────────────────────────────────────
          Data Extraction Layer
────────────────────────────────────────
                        │
                        ▼
             Normalization Engine
                        │
                        ▼
               Merge Engine
                        │
                        ▼
          Confidence Scoring Engine
                        │
                        ▼
           Provenance Tracking
                        │
                        ▼
             Validation Engine
                        │
                        ▼
            Config Projection Layer
                        │
                        ▼
        candidate.json + pipeline_report.json
```

---

# ⚙️ Technology Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11 | Core Programming Language |
| Pydantic v2 | Schema Validation |
| PyMuPDF | Resume Parsing |
| PyGithub | GitHub Profile Extraction |
| Requests | REST API Communication |
| RapidFuzz | Skill Normalization |
| Phonenumbers | Phone Validation |
| Dateutil | Date Normalization |
| JSON Schema | Configuration Validation |
| Pytest | Unit Testing |

---

# 📂 Project Structure

```text
candidate-fusion-ai/

├── config/
├── docs/
├── engine/
├── input/
├── logs/
├── output/
├── parsers/
├── tests/
├── utils/

├── main.py
├── requirements.txt
├── README.md
└── .gitignore
```

---

# 🔄 Pipeline Workflow

```
Input Sources

↓

Data Parsing

↓

Normalization

↓

Merge Engine

↓

Conflict Resolution

↓

Confidence Scoring

↓

Provenance Tracking

↓

Validation

↓

Projection Layer

↓

Canonical Candidate Profile
```

---

# 📥 Supported Input Sources

### 📊 Structured Sources

- Recruiter CSV Export
- ATS JSON Export

### 📄 Unstructured Sources

- Resume PDF
- GitHub Public Profile

---

# 📤 Output

The pipeline generates:

```
candidate.json
```

Canonical Candidate Profile

```
pipeline_report.json
```

Pipeline execution statistics

---

# 📊 Confidence Scoring

Every candidate attribute receives an independent confidence score based on:

- Source Reliability
- Data Completeness
- Cross-source Agreement
- Validation Quality

An overall confidence score is then computed for the complete candidate profile.

---

# 📍 Provenance Tracking

Each output field stores:

- Original Source
- Extraction Method
- Raw Value
- Confidence Score

This enables complete explainability and traceability across the pipeline.

---

# ⚙️ Configuration Support

CandidateFusion supports runtime configuration through JSON files.

Current configuration options include:

- Field Projection
- Skill Canonicalization
- Confidence Weights
- Field Aliases
- Hidden Metadata
- Output Customization

---

# 🚀 Getting Started

Clone the repository

```bash
git clone https://github.com/yourusername/candidate-fusion-ai.git
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run

```bash
python main.py \
--csv input/recruiter.csv \
--json input/ats.json \
--resume input/resume.pdf \
--github octocat \
--config config/projection.json
```

---

# 🧪 Testing

Run all tests

```bash
pytest
```

---

# 📈 Future Enhancements

- LinkedIn Integration
- OCR Support for Scanned Resumes
- Batch Candidate Processing
- Docker Deployment
- REST API Service
- Web Dashboard
- AI-based Skill Extraction
- Candidate Similarity Search

---

# 👩‍💻 Author

**Pranathi Yadav**

B.E. Computer Science Engineering (AI & ML)

Chaitanya Bharathi Institute of Technology

---

# ⭐ If you found this project interesting, consider giving it a star!