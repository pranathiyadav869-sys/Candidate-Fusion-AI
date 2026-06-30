# CandidateFusion — Design Document

**Version:** 1.0.0 | **Author:** CandidateFusion Team | **Status:** Production

---

## 1. Problem Statement

Recruiting teams collect candidate data from multiple heterogeneous sources:

| Source | Format | Quality | Coverage |
|--------|--------|---------|----------|
| PDF Resume | Unstructured text | High accuracy (self-authored) | Name, skills, experience, education |
| ATS Export | JSON (varies by vendor) | Medium-high (validated on submission) | All fields, vendor-specific schema |
| Recruiter CSV | Tabular | Medium (manual entry, typos) | Core fields only |
| GitHub Profile | REST API | High factual accuracy | Skills (via languages), links |

**The core problem:** Each source has a different schema, different field names, different quality level, and often conflicting values for the same field. A recruiter currently reconciles these manually — an error-prone, time-consuming process.

**CandidateFusion automates this:** it ingests all sources, normalizes data to a canonical schema, resolves conflicts deterministically using a priority-based strategy, scores confidence per field and overall, tracks full provenance, and outputs a single validated `candidate.json`.

---

## 2. Architecture

### Layered Design

```
┌──────────────┐
│    CLI / API │  main.py, projector.py
├──────────────┤
│   Parsers    │  resume_parser, ats_parser, csv_parser, github_parser
├──────────────┤
│    Engine    │  merge, confidence, normalize, provenance, validator
├──────────────┤
│    Schema    │  schema.py (Pydantic v2 CandidateProfile)
├──────────────┤
│    Utils     │  constants, exceptions, helpers, logger
└──────────────┘
```

### Key Principles
- **Parsers are dumb:** Each parser returns a canonical `dict[str, Any]` with no business logic.
- **Engine is stateless:** All engine functions are pure (given same inputs → same output).
- **Config-driven behaviour:** Source weights, field aliases, and output structure are in JSON configs,
  not hardcoded.
- **No silent failures:** Every dropped value is logged. Every conflict is recorded in provenance.
- **Partial data is fine:** Every field is Optional; a parse that only extracts 3 fields still contributes.

---

## 3. Pipeline

```
Step 1: Parse
  For each provided source:
    → Call the appropriate parser
    → Parser returns canonical dict
    → Log success or failure; continue on failure

Step 2: Merge  (engine/merge.py)
  For scalar fields (name, location, headline, years_experience):
    → Pick value from highest-priority source that has a non-null value
    → Record all candidates in provenance
    → Mark winner in provenance

  For list fields (emails, phones, skills, links):
    → UNION all values from all sources
    → Normalize each value (lowercase email, E.164 phone, canonical skill name)
    → Deduplicate after normalization

  For structured lists (experience, education):
    → Deduplicate by fingerprint: (company, title) for experience; (institution, degree) for education
    → Higher-priority source wins on collision
    → Sort by start_date desc (most recent first)

Step 3: Confidence Scoring
  For each field:
    → Start with source baseline score
    → Apply field quality rules (e.g. +0.05 if name has multiple words)
    → Apply cross-source agreement bonus (+0.02 per additional agreeing source)
    → Clamp to [0.0, 1.0]

  Overall confidence:
    → Weighted average of key field confidences
    → Bonus for multiple sources (+0.02 per source, max +0.08)
    → Penalties for missing name (-0.10) or missing email (-0.08)

Step 4: Validate  (engine/validator.py)
  → Drop invalid emails (regex check)
  → Drop non-E.164 phones
  → Drop unrealistic years_experience (> 60 or < 0)
  → Drop skills with empty canonical_name
  → Drop experience entries with no company AND no title
  → Drop education entries with no institution
  → Clamp overall_confidence to [0.0, 1.0]
  → Generate candidate_id if missing

Step 5: Project & Output  (engine/projector.py)
  → Apply projection.json rules:
     - Rename fields via field_aliases
     - Remove fields in exclude_fields
     - Optionally hide provenance or confidence
  → Write candidate.json
  → Write pipeline_report.json
```

---

## 4. Design Decisions

### 4.1 Why Pydantic v2 for the Schema?

- Runtime validation at the boundary (Pydantic catches type errors immediately)
- `.model_dump()` gives clean JSON-serializable output
- Field validators handle deduplication (emails, phones)
- Clear, self-documenting schema that serves as contract between pipeline stages

**Trade-off:** Pydantic v2 has a steeper learning curve than a plain dataclass, and the migration
from v1 can be painful. We accepted this cost for the validation benefits.

### 4.2 Why Source Priority over Voting?

**Alternative considered:** Majority voting (if 2/3 sources agree, use that value).
**Problem:** With 2-3 sources, ties are common. Priority is deterministic and explainable.
**Our approach:** Priority order (Resume > ATS > GitHub > CSV > Derived) reflects empirical data
quality. A resume is human-curated for accuracy; CSV is manually entered and may have typos.

**Trade-off:** A high-quality CSV can be overridden by a poor resume. Mitigated by: (a) the
confidence score surfacing the conflict, and (b) the `projection.json` letting operators override.

### 4.3 Why Union (not Intersect) for List Fields?

A resume might only have a work email. The ATS might have a personal email the candidate added.
A CSV might have a phone number the resume omitted. **We want all valid contact information.**

For skills: a recruiter CSV might list `Django` as a skill the resume forgot to mention. We include
it (with lower confidence from the CSV source) and let the downstream consumer decide on threshold.

### 4.4 Why Separate Normalize Module?

All normalization (email, phone, name, skill, location, date, URL, years_experience) lives in one
place (`engine/normalize.py`). This ensures:
- Parsers don't embed normalization logic
- Normalization is tested in isolation
- A single fix propagates everywhere

### 4.5 Why PyMuPDF (fitz) for PDF Parsing?

- Fastest Python PDF text extractor by a large margin
- Handles multi-column layouts better than pypdf
- Actively maintained
- No OCR (assumes digitally-created PDFs) — this is a documented limitation

**Trade-off:** Does not handle scanned/image PDFs. For OCR, a Tesseract step would need to be added.

### 4.6 Why PyGithub + requests fallback?

PyGithub provides a high-level API with automatic rate limit handling. The requests fallback ensures
the parser still works in environments where PyGithub is not installed (e.g. lightweight containers).
The strategy: try PyGithub first, catch ImportError, fall back to raw HTTP.

---

## 5. Conflict Resolution Strategy

| Field Type | Strategy | Example |
|---|---|---|
| Scalar (name, location, headline) | Highest-priority non-null source wins | Resume "Priya Sharma" > CSV "priya s." |
| Email list | Union + normalize + dedup | resume + ats = 2 unique emails |
| Phone list | Union + E.164 normalize + dedup | 2 sources, same number → 1 entry |
| Skill list | Union + canonical alias + dedup by canonical_name | "py" + "Python" → 1 "Python" entry |
| Experience | Dedup by (company.lower, title.lower) fingerprint; higher source wins | "acme/engineer" from resume beats "ACME/ENGINEER" from CSV |
| Education | Dedup by (institution.lower, degree.lower); higher source wins | Same pattern |

---

## 6. Confidence Scoring

### Source Baselines

| Source | Baseline | Rationale |
|--------|---------|-----------|
| Resume | 0.95 | Human-curated for accuracy, primary source |
| ATS | 0.90 | Validated on submission, but data entry may have errors |
| GitHub | 0.88 | Factual but limited scope (skills/links only) |
| CSV | 0.82 | Manual recruiter entry, highest error rate |
| Derived | 0.70 | Computed (e.g. YOE from experience entries) |

### Field Quality Modifiers

Applied as additive deltas on top of the baseline:
- `full_name`: +0.05 if has ≥ 2 words; -0.05 if > 30 characters
- `emails`: +0.03 if non-empty; -0.05 if > 3 emails (suspicious)
- `years_experience`: +0.03 if in [0, 50]; -0.10 if > 40 (unrealistic)
- `skills`: +0.03 if ≥ 3; +0.02 additional if ≥ 10

### Cross-Source Agreement

Each additional source that agrees on a value adds +0.02 (max +0.10).
Example: name "Priya Sharma" from resume (0.95) + agreed by ATS + CSV = 0.95 + 0.04 = 0.99.

### Overall Confidence Formula

```
weighted_avg = Σ(field_confidence[f] × weight[f]) / Σ(weight[f])

where weights = {
  full_name: 0.20, emails: 0.20, phones: 0.10,
  skills: 0.15, experience: 0.15, education: 0.10,
  location: 0.05, years_experience: 0.05
}

source_bonus = min(n_sources × 0.02, 0.08)
penalty = 0.10 if no name else 0 + 0.08 if no email else 0

overall = clamp(weighted_avg + source_bonus - penalty, 0.0, 1.0)
```

---

## 7. Provenance Tracking

Every field value has a `FieldProvenance` object recording:

```json
{
  "selected_source": "resume",
  "entries": [
    {"source": "resume", "method": "direct_field", "raw_value": "Priya Sharma", "confidence": 0.9975},
    {"source": "ats",    "method": "direct_field", "raw_value": "Priya Sharma", "confidence": 0.9475},
    {"source": "csv",    "method": "direct_field", "raw_value": "priya s.",      "confidence": 0.8225}
  ],
  "confidence": 0.9975
}
```

This enables a recruiter to:
- Audit every value in the output
- Understand why one source was preferred over another
- Detect when sources significantly disagree (potential data quality issue)

---

## 8. Validation

Validation runs **after** merge, not during parsing. Rationale:

- Parsers can be lenient — accept anything parseable
- The contract is enforced in one place (validator.py)
- Validation warnings are logged and included in the pipeline report

Rules enforced:
1. Email must match RFC-5321 regex
2. Phone must start with `+` (E.164)
3. `years_experience` must be in [0, 60]
4. `full_name` must be ≥ 2 characters
5. `skills` must have non-empty `canonical_name`
6. `experience` entries must have at least company OR title
7. `education` entries must have institution
8. `overall_confidence` clamped to [0.0, 1.0]

---

## 9. Future Improvements

### Short-term (1–2 sprints)
- Wire `rapidfuzz` into `normalize_skill()` for fuzzy matching unknown skills
- Batch CSV processing: all rows → multiple candidate profiles
- REST API (FastAPI) wrapping the pipeline
- `_source_data` field properly declared as Pydantic `PrivateAttr`

### Medium-term (1–2 quarters)
- Database persistence (PostgreSQL) with candidate deduplication across pipeline runs
- LinkedIn PDF/HTML parser
- Webhook support: trigger pipeline on new ATS event
- ML-based name extraction from resume header (replace heuristic regex)

### Long-term (6+ months)
- Multi-language resume support (spaCy NER models)
- Candidate deduplication across multiple candidates (entity resolution)
- Active learning: use recruiter feedback to improve confidence weights
- Support for DOCX and RTF resumes
