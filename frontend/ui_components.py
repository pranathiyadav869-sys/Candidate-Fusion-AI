# # frontend/ui_components.py
# """
# Display components for CandidateFusion AI.

# Each function renders one section of the candidate profile. They take
# the data they need (a CandidateProfile, or pieces of one) and render
# directly via Streamlit — no business logic, no calls back into the
# pipeline. New sections are added here one function at a time as we
# build out Steps 6-10.
# """

# from __future__ import annotations

# import streamlit as st
# import textwrap

# from engine.schema import CandidateProfile


# def _confidence_color(score: float) -> str:
#     """Map a 0.0-1.0 confidence score to a semantic color, matching the
#     thresholds used elsewhere (green/amber/red)."""
#     if score >= 0.75:
#         return "#16A34A"  # success
#     if score >= 0.5:
#         return "#D97706"  # warning
#     return "#DC2626"      # danger
# def render_identity_header(profile: CandidateProfile) -> None:
#     """Render the candidate identity card and confidence score."""

#     name = profile.full_name or "Unnamed Candidate"
#     headline = profile.headline or ""
#     emails = ", ".join(profile.emails) if profile.emails else "—"
#     phones = ", ".join(profile.phones) if profile.phones else "—"
#     location = profile.location or "—"

#     headline_html = ""
#     if headline:
#         headline_html = (
#             f'<div style="font-size:1rem; color:#2563EB; '
#             f'font-weight:600; margin-top:0.2rem;">{headline}</div>'
#         )

#     html = f"""
# <div class="cf-card">
#     <div style="font-size:1.6rem; font-weight:800; color:#1E293B;">
#         {name}
#     </div>

#     {headline_html}

#     <div style="display:flex; gap:2rem; flex-wrap:wrap; margin-top:1rem;">

#         <div>
#             <div class="cf-muted">Email</div>
#             <div>{emails}</div>
#         </div>

#         <div>
#             <div class="cf-muted">Phone</div>
#             <div>{phones}</div>
#         </div>

#         <div>
#             <div class="cf-muted">Location</div>
#             <div>{location}</div>
#         </div>

#     </div>
# </div>
# """

#     st.markdown(textwrap.dedent(html), unsafe_allow_html=True)

#     score = profile.overall_confidence or 0.0
#     color = _confidence_color(score)

#     st.markdown(
#         textwrap.dedent(
#             f"""
# <div style="display:flex;justify-content:space-between;
#             align-items:center;margin-top:1rem;margin-bottom:0.4rem;">
#     <span style="font-weight:600;color:#1E293B;">
#         Overall Confidence
#     </span>
#     <span style="font-weight:700;color:{color};">
#         {score:.0%}
#     </span>
# </div>
# """
#         ),
#         unsafe_allow_html=True,
#     )

#     st.progress(score)

# # def render_identity_header(profile: CandidateProfile) -> None:
# #     """Name, headline, contact details, and the overall confidence bar."""

# #     name = profile.full_name or "Unnamed Candidate"
# #     headline = profile.headline or ""
# #     emails = ", ".join(profile.emails) if profile.emails else "—"
# #     phones = ", ".join(profile.phones) if profile.phones else "—"
# #     location = profile.location or "—"

# #     st.markdown(
# #         f"""
# #         <div class="cf-card">
# #             <div style="font-size:1.5rem; font-weight:800; color:#1E293B;">
# #                 {name}
# #             </div>
# #             {f'<div style="font-size:1rem; color:#2563EB; font-weight:600; margin-top:0.15rem;">{headline}</div>' if headline else ''}
# #             <div style="margin-top:0.7rem; display:flex; gap:1.8rem; flex-wrap:wrap;">
# #                 <div>
# #                     <div class="cf-muted">Email</div>
# #                     <div>{emails}</div>
# #                 </div>
# #                 <div>
# #                     <div class="cf-muted">Phone</div>
# #                     <div>{phones}</div>
# #                 </div>
# #                 <div>
# #                     <div class="cf-muted">Location</div>
# #                     <div>{location}</div>
# #                 </div>
# #             </div>
# #         </div>
# #         """,
# #         unsafe_allow_html=True,
# #     )

# #     score = profile.overall_confidence or 0.0
# #     color = _confidence_color(score)

# #     st.markdown(
# #         f"""
# #         <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.9rem; margin-bottom:0.25rem;">
# #             <span style="font-weight:600; color:#1E293B;">Overall Confidence</span>
# #             <span style="font-weight:700; color:{color};">{score:.0%}</span>
# #         </div>
# #         """,
# #         unsafe_allow_html=True,
# #     )
# #     st.progress(min(max(score, 0.0), 1.0))
# def render_skills(profile: CandidateProfile) -> None:
#     """Skills as rounded pill tags, sorted by confidence (highest first)."""

#     st.markdown('<div class="cf-section-title">Skills</div>', unsafe_allow_html=True)

#     if not profile.skills:
#         st.markdown('<span class="cf-muted">No skills detected.</span>', unsafe_allow_html=True)
#         return

#     sorted_skills = sorted(profile.skills, key=lambda s: s.confidence, reverse=True)

#     tags_html = "".join(
#         f'<span class="cf-skill-tag">{skill.name}</span>' for skill in sorted_skills
#     )
#     st.markdown(f'<div>{tags_html}</div>', unsafe_allow_html=True)    
# def render_experience(profile: CandidateProfile) -> None:
#     """One expander per experience entry, title/company visible when collapsed."""

#     st.markdown('<div class="cf-section-title">Experience</div>', unsafe_allow_html=True)

#     if not profile.experience:
#         st.markdown('<span class="cf-muted">No experience entries found.</span>', unsafe_allow_html=True)
#         return

#     for entry in profile.experience:
#         title = entry.title or "Unknown Role"
#         company = entry.company or "Unknown Company"
#         start = entry.start_date or "—"
#         end = entry.end_date or "Present"

#         with st.expander(f"{title}  ·  {company}  ({start} – {end})"):
#             if entry.location:
#                 st.markdown(f'<span class="cf-muted">📍 {entry.location}</span>', unsafe_allow_html=True)
#             if entry.description:
#                 st.write(entry.description)
#             elif not entry.location:
#                 st.markdown('<span class="cf-muted">No further details available.</span>', unsafe_allow_html=True)


# def render_education(profile: CandidateProfile) -> None:
#     """One expander per education entry, degree/institution visible when collapsed."""

#     st.markdown('<div class="cf-section-title">Education</div>', unsafe_allow_html=True)

#     if not profile.education:
#         st.markdown('<span class="cf-muted">No education entries found.</span>', unsafe_allow_html=True)
#         return

#     for entry in profile.education:
#         degree = entry.degree or "Unknown Degree"
#         institution = entry.institution or "Unknown Institution"
#         start = entry.start_date or "—"
#         end = entry.end_date or "—"

#         with st.expander(f"{degree}  ·  {institution}  ({start} – {end})"):
#             if entry.field_of_study:
#                 st.markdown(f"**Field of study:** {entry.field_of_study}")
#             if entry.gpa is not None:
#                 st.markdown(f"**GPA:** {entry.gpa}")
#             if not entry.field_of_study and entry.gpa is None:
#                 st.markdown('<span class="cf-muted">No further details available.</span>', unsafe_allow_html=True)    
# def render_github_info(profile: CandidateProfile, sources_used: list) -> None:
#     """
#     GitHub section. CandidateProfile has no dedicated `github` object, so
#     this surfaces what's actually available: the GitHub link (if merged
#     in) and whether a GitHub source was used in this run.
#     """
#     st.markdown('<div class="cf-section-title">GitHub Information</div>', unsafe_allow_html=True)

#     github_links = [link for link in profile.links if (link.label or "").lower() == "github"]
#     github_used = any(src.startswith("github:") for src in sources_used)

#     if not github_links and not github_used:
#         st.markdown(
#             '<span class="cf-muted">No GitHub source was used for this profile.</span>',
#             unsafe_allow_html=True,
#         )
#         return

#     if github_used:
#         github_source = next((s for s in sources_used if s.startswith("github:")), None)
#         username = github_source.split(":", 1)[1] if github_source else None
#         if username:
#             st.markdown(f"**GitHub username:** `{username}`")

#     for link in github_links:
#         st.markdown(f"🔗 [{link.url}]({link.url})")

#     if not github_links:
#         st.markdown(
#             '<span class="cf-muted">GitHub data contributed to this profile, '
#             'but no public profile link was captured.</span>',
#             unsafe_allow_html=True,
#         )


# def render_sources_used(sources_used: list) -> None:
#     """Pills showing which sources successfully contributed to this profile."""

#     st.markdown('<div class="cf-section-title">Sources Used</div>', unsafe_allow_html=True)

#     if not sources_used:
#         st.markdown('<span class="cf-muted">No sources recorded.</span>', unsafe_allow_html=True)
#         return

#     pills_html = "".join(
#         f'<span class="cf-pill-success" style="margin-right:0.4rem;">{src}</span>'
#         for src in sources_used
#     )
#     st.markdown(f"<div>{pills_html}</div>", unsafe_allow_html=True)


# def render_validation_warnings(warnings: list) -> None:
#     """Validation/parse warnings, tucked into a collapsed expander."""

#     label = f"⚠️ Validation Warnings ({len(warnings)})" if warnings else "✅ Validation Warnings (none)"

#     with st.expander(label, expanded=False):
#         if not warnings:
#             st.markdown('<span class="cf-muted">No warnings were raised during this run.</span>', unsafe_allow_html=True)
#         else:
#             for w in warnings:
#                 st.markdown(f'<span class="cf-pill-warning">⚠</span>&nbsp; {w}', unsafe_allow_html=True)                


# from pathlib import Path


# def render_downloads(candidate_json_path, report_json_path) -> None:
#     """
#     Download buttons for the two files run_pipeline() already wrote to
#     disk. We read them back as bytes rather than re-serializing the
#     profile ourselves, so the download is byte-identical to what the
#     backend produced.
#     """
#     st.markdown('<div class="cf-section-title">Downloads</div>', unsafe_allow_html=True)

#     col1, col2 = st.columns(2)

#     candidate_path = Path(candidate_json_path)
#     report_path = Path(report_json_path)

#     with col1:
#         if candidate_path.exists():
#             st.download_button(
#                 "⬇ Download candidate.json",
#                 data=candidate_path.read_bytes(),
#                 file_name="candidate.json",
#                 mime="application/json",
#                 use_container_width=True,
#             )
#         else:
#             st.markdown('<span class="cf-muted">candidate.json not found.</span>', unsafe_allow_html=True)

#     with col2:
#         if report_path.exists():
#             st.download_button(
#                 "⬇ Download pipeline_report.json",
#                 data=report_path.read_bytes(),
#                 file_name="pipeline_report.json",
#                 mime="application/json",
#                 use_container_width=True,
#             )
#         else:
#             st.markdown('<span class="cf-muted">pipeline_report.json not found.</span>', unsafe_allow_html=True)
# frontend/ui_components.py
"""
Display components for CandidateFusion AI.

Root Cause Fix (textwrap.dedent bug)
--------------------------------------
The original render_identity_header passed its HTML through textwrap.dedent()
before handing it to st.markdown(). The f-string opened with a literal newline,
so dedent found no common leading whitespace to strip. CommonMark (the Markdown
dialect Streamlit uses) then interpreted any line that begins with 4+ spaces of
indentation as a *fenced code block*, which is why the raw HTML source was
printed instead of rendered.

Rule: **never wrap HTML strings for st.markdown in textwrap.dedent**.
Write them as plain f-strings. The outer <div> must start at column 0 in the
string (leading newlines are fine; leading spaces are not).

All other functions in this file used bare string literals and worked correctly —
only render_identity_header and its confidence row were affected.

Design notes
------------
- Every component is self-contained: inline styles provide the base appearance.
  The cf-* CSS classes are *additive*; if the main app injects the stylesheet
  they will override/enhance the inline styles, but components render correctly
  even without the stylesheet.
- No business logic here. Components receive data and render it, period.
- `unsafe_allow_html=True` is required for every st.markdown call that contains
  HTML. Streamlit silently strips tags when it is omitted — never omit it.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from engine.schema import CandidateProfile


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _confidence_color(score: float) -> str:
    """Map a 0.0-1.0 score to a semantic hex color."""
    if score >= 0.75:
        return "#16A34A"   # green
    if score >= 0.50:
        return "#D97706"   # amber
    return "#DC2626"       # red


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Identity Header
# ---------------------------------------------------------------------------

def render_identity_header(profile: CandidateProfile) -> None:
    """
    Candidate name, headline, contact row, and overall-confidence bar.

    FIX: removed textwrap.dedent(). The HTML string is written as a plain
    f-string. The opening <div> sits at column 0 inside the string so
    CommonMark never mistakes it for a code block.
    """
    name     = profile.full_name or "Unnamed Candidate"
    headline = profile.headline  or ""
    emails   = ", ".join(profile.emails) if profile.emails else "—"
    phones   = ", ".join(profile.phones) if profile.phones else "—"
    location = profile.location or "—"

    # Build optional headline row — must itself contain no leading spaces
    headline_row = ""
    if headline:
        headline_row = (
            f'<div class="cf-headline" style="'
            f'font-size:1rem;color:#2563EB;font-weight:600;margin-top:0.25rem;">'
            f'{headline}</div>'
        )

    # -----------------------------------------------------------------------
    # KEY FIX: the string below starts at column 0 inside the triple-quote.
    # Do NOT indent these lines with spaces — that is what triggered the
    # CommonMark code-block interpretation.
    # -----------------------------------------------------------------------
    card_html = (
        f'<div class="cf-card" style="'
        f'background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;'
        f'padding:1.25rem 1.5rem;margin-bottom:0.5rem;">'
        f'<div class="cf-name" style="font-size:1.6rem;font-weight:800;color:#1E293B;'
        f'letter-spacing:-0.02em;">{name}</div>'
        f'{headline_row}'
        f'<div style="display:flex;gap:2.5rem;flex-wrap:wrap;margin-top:1rem;">'

        f'<div>'
        f'<div class="cf-muted" style="font-size:0.72rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.06em;color:#64748B;'
        f'margin-bottom:0.15rem;">Email</div>'
        f'<div style="color:#1E293B;font-size:0.9rem;">{emails}</div>'
        f'</div>'

        f'<div>'
        f'<div class="cf-muted" style="font-size:0.72rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.06em;color:#64748B;'
        f'margin-bottom:0.15rem;">Phone</div>'
        f'<div style="color:#1E293B;font-size:0.9rem;">{phones}</div>'
        f'</div>'

        f'<div>'
        f'<div class="cf-muted" style="font-size:0.72rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.06em;color:#64748B;'
        f'margin-bottom:0.15rem;">Location</div>'
        f'<div style="color:#1E293B;font-size:0.9rem;">{location}</div>'
        f'</div>'

        f'</div>'   # end contact row
        f'</div>'   # end cf-card
    )

    st.markdown(card_html, unsafe_allow_html=True)

    # --- Confidence bar ---
    score = profile.overall_confidence or 0.0
    color = _confidence_color(score)
    label = _confidence_label(score)

    # Plain f-string, outer div at column 0 of the string value
    conf_html = (
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;margin-top:1rem;margin-bottom:0.35rem;">'
        f'<span style="font-weight:600;color:#1E293B;font-size:0.9rem;">'
        f'Overall Confidence</span>'
        f'<span style="font-weight:700;color:{color};font-size:0.9rem;">'
        f'{score:.0%}&nbsp;<span style="font-weight:400;font-size:0.8rem;'
        f'color:{color};">({label})</span></span>'
        f'</div>'
    )
    st.markdown(conf_html, unsafe_allow_html=True)
    st.progress(min(max(score, 0.0), 1.0))


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def render_skills(profile: CandidateProfile) -> None:
    """Skill pills sorted by confidence descending, with source badges."""

    st.markdown(
        '<div class="cf-section-title" style="font-size:1rem;font-weight:700;'
        'color:#1E293B;margin:1.5rem 0 0.6rem;">Skills</div>',
        unsafe_allow_html=True,
    )

    if not profile.skills:
        st.markdown(
            '<span class="cf-muted" style="color:#64748B;font-size:0.88rem;">'
            'No skills detected.</span>',
            unsafe_allow_html=True,
        )
        return

    sorted_skills = sorted(profile.skills, key=lambda s: s.confidence, reverse=True)

    pills = []
    for skill in sorted_skills:
        conf_pct = int(skill.confidence * 100)
        # Color the pill border by confidence tier
        if skill.confidence >= 0.90:
            border = "#16A34A"
            bg     = "#F0FDF4"
        elif skill.confidence >= 0.75:
            border = "#2563EB"
            bg     = "#EFF6FF"
        else:
            border = "#94A3B8"
            bg     = "#F8FAFC"

        pills.append(
            f'<span class="cf-skill-tag" title="{conf_pct}% confidence" style="'
            f'display:inline-block;margin:0.2rem;padding:0.3rem 0.75rem;'
            f'border-radius:9999px;border:1.5px solid {border};background:{bg};'
            f'color:#1E293B;font-size:0.82rem;font-weight:500;'
            f'white-space:nowrap;cursor:default;">'
            f'{skill.canonical_name}'
            f'</span>'
        )

    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:0.1rem;margin-top:0.25rem;">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------

def render_experience(profile: CandidateProfile) -> None:
    """Timeline-style experience entries, each in a collapsible expander."""

    st.markdown(
        '<div class="cf-section-title" style="font-size:1rem;font-weight:700;'
        'color:#1E293B;margin:1.5rem 0 0.6rem;">Experience</div>',
        unsafe_allow_html=True,
    )

    if not profile.experience:
        st.markdown(
            '<span class="cf-muted" style="color:#64748B;font-size:0.88rem;">'
            'No experience entries found.</span>',
            unsafe_allow_html=True,
        )
        return

    for entry in profile.experience:
        title   = entry.title   or "Unknown Role"
        company = entry.company or "Unknown Company"
        start   = entry.start_date or "—"
        end     = entry.end_date   or "Present"

        with st.expander(f"{title}  ·  {company}  ({start} – {end})"):
            if entry.location:
                st.markdown(
                    f'<span style="color:#64748B;font-size:0.85rem;">📍 {entry.location}</span>',
                    unsafe_allow_html=True,
                )
            if entry.description:
                st.write(entry.description)
            elif not entry.location:
                st.markdown(
                    '<span style="color:#64748B;font-size:0.85rem;">'
                    'No further details available.</span>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

def render_education(profile: CandidateProfile) -> None:
    """Education entries in collapsible expanders."""

    st.markdown(
        '<div class="cf-section-title" style="font-size:1rem;font-weight:700;'
        'color:#1E293B;margin:1.5rem 0 0.6rem;">Education</div>',
        unsafe_allow_html=True,
    )

    if not profile.education:
        st.markdown(
            '<span class="cf-muted" style="color:#64748B;font-size:0.88rem;">'
            'No education entries found.</span>',
            unsafe_allow_html=True,
        )
        return

    for entry in profile.education:
        degree      = entry.degree      or "Unknown Degree"
        institution = entry.institution or "Unknown Institution"
        start       = entry.start_date  or "—"
        end         = entry.end_date    or "—"

        with st.expander(f"{degree}  ·  {institution}  ({start} – {end})"):
            if entry.field_of_study:
                st.markdown(f"**Field of study:** {entry.field_of_study}")
            if entry.gpa is not None:
                st.markdown(f"**GPA:** {entry.gpa:.2f}")
            if not entry.field_of_study and entry.gpa is None:
                st.markdown(
                    '<span style="color:#64748B;font-size:0.85rem;">'
                    'No further details available.</span>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# GitHub Information
# ---------------------------------------------------------------------------

def render_github_info(profile: CandidateProfile, sources_used: list) -> None:
    """GitHub link and contribution summary."""

    st.markdown(
        '<div class="cf-section-title" style="font-size:1rem;font-weight:700;'
        'color:#1E293B;margin:1.5rem 0 0.6rem;">GitHub Information</div>',
        unsafe_allow_html=True,
    )

    github_links = [
        link for link in profile.links
        if (link.label or "").lower() == "github"
    ]
    github_used = any(src.startswith("github:") for src in sources_used)

    if not github_links and not github_used:
        st.markdown(
            '<span style="color:#64748B;font-size:0.88rem;">'
            'No GitHub source was used for this profile.</span>',
            unsafe_allow_html=True,
        )
        return

    if github_used:
        github_source = next(
            (s for s in sources_used if s.startswith("github:")), None
        )
        username = github_source.split(":", 1)[1] if github_source else None
        if username:
            st.markdown(f"**GitHub username:** `{username}`")

    for link in github_links:
        st.markdown(f"🔗 [{link.url}]({link.url})")

    if not github_links:
        st.markdown(
            '<span style="color:#64748B;font-size:0.88rem;">'
            'GitHub data contributed to this profile, '
            'but no public profile link was captured.</span>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Sources Used
# ---------------------------------------------------------------------------

def render_sources_used(sources_used: list) -> None:
    """Pill badges for every source that contributed to this profile."""

    st.markdown(
        '<div class="cf-section-title" style="font-size:1rem;font-weight:700;'
        'color:#1E293B;margin:1.5rem 0 0.6rem;">Sources Used</div>',
        unsafe_allow_html=True,
    )

    if not sources_used:
        st.markdown(
            '<span style="color:#64748B;font-size:0.88rem;">'
            'No sources recorded.</span>',
            unsafe_allow_html=True,
        )
        return

    pills = "".join(
        f'<span class="cf-pill-success" style="'
        f'display:inline-block;margin-right:0.4rem;padding:0.25rem 0.7rem;'
        f'border-radius:9999px;background:#DCFCE7;color:#15803D;'
        f'font-size:0.8rem;font-weight:600;">{src}</span>'
        for src in sources_used
    )
    st.markdown(f'<div style="margin-top:0.25rem;">{pills}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Validation Warnings
# ---------------------------------------------------------------------------

def render_validation_warnings(warnings: list) -> None:
    """Collapsible list of validation/parse warnings."""

    if warnings:
        label = f"⚠️ Validation Warnings ({len(warnings)})"
    else:
        label = "✅ Validation Warnings (none)"

    with st.expander(label, expanded=False):
        if not warnings:
            st.markdown(
                '<span style="color:#64748B;font-size:0.88rem;">'
                'No warnings were raised during this run.</span>',
                unsafe_allow_html=True,
            )
        else:
            for w in warnings:
                st.markdown(
                    f'<div style="display:flex;align-items:flex-start;gap:0.5rem;'
                    f'margin-bottom:0.4rem;">'
                    f'<span style="display:inline-block;padding:0.1rem 0.45rem;'
                    f'border-radius:4px;background:#FEF9C3;color:#92400E;'
                    f'font-size:0.75rem;font-weight:700;flex-shrink:0;">⚠</span>'
                    f'<span style="font-size:0.85rem;color:#1E293B;">{w}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

def render_downloads(candidate_json_path: str, report_json_path: str) -> None:
    """
    Download buttons for candidate.json and pipeline_report.json.
    Files are read from disk as bytes so the download is byte-identical
    to what the backend produced.
    """
    st.markdown(
        '<div class="cf-section-title" style="font-size:1rem;font-weight:700;'
        'color:#1E293B;margin:1.5rem 0 0.6rem;">Downloads</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    candidate_path = Path(candidate_json_path)
    report_path    = Path(report_json_path)

    with col1:
        if candidate_path.exists():
            st.download_button(
                "⬇ Download candidate.json",
                data=candidate_path.read_bytes(),
                file_name="candidate.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.markdown(
                '<span style="color:#64748B;font-size:0.85rem;">'
                'candidate.json not found.</span>',
                unsafe_allow_html=True,
            )

    with col2:
        if report_path.exists():
            st.download_button(
                "⬇ Download pipeline_report.json",
                data=report_path.read_bytes(),
                file_name="pipeline_report.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.markdown(
                '<span style="color:#64748B;font-size:0.85rem;">'
                'pipeline_report.json not found.</span>',
                unsafe_allow_html=True,
            )