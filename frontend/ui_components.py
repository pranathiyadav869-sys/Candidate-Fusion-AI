# frontend/ui_components.py
"""
Display components for CandidateFusion AI.

Each function renders one section of the candidate profile. They take
the data they need (a CandidateProfile, or pieces of one) and render
directly via Streamlit — no business logic, no calls back into the
pipeline. New sections are added here one function at a time as we
build out Steps 6-10.
"""

from __future__ import annotations

import streamlit as st

from engine.schema import CandidateProfile


def _confidence_color(score: float) -> str:
    """Map a 0.0-1.0 confidence score to a semantic color, matching the
    thresholds used elsewhere (green/amber/red)."""
    if score >= 0.75:
        return "#16A34A"  # success
    if score >= 0.5:
        return "#D97706"  # warning
    return "#DC2626"      # danger


def render_identity_header(profile: CandidateProfile) -> None:
    """Name, headline, contact details, and the overall confidence bar."""

    name = profile.full_name or "Unnamed Candidate"
    headline = profile.headline or ""
    emails = ", ".join(profile.emails) if profile.emails else "—"
    phones = ", ".join(profile.phones) if profile.phones else "—"
    location = profile.location or "—"

    st.markdown(
        f"""
        <div class="cf-card">
            <div style="font-size:1.5rem; font-weight:800; color:#1E293B;">
                {name}
            </div>
            {f'<div style="font-size:1rem; color:#2563EB; font-weight:600; margin-top:0.15rem;">{headline}</div>' if headline else ''}
            <div style="margin-top:0.7rem; display:flex; gap:1.8rem; flex-wrap:wrap;">
                <div>
                    <div class="cf-muted">Email</div>
                    <div>{emails}</div>
                </div>
                <div>
                    <div class="cf-muted">Phone</div>
                    <div>{phones}</div>
                </div>
                <div>
                    <div class="cf-muted">Location</div>
                    <div>{location}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    score = profile.overall_confidence or 0.0
    color = _confidence_color(score)

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.9rem; margin-bottom:0.25rem;">
            <span style="font-weight:600; color:#1E293B;">Overall Confidence</span>
            <span style="font-weight:700; color:{color};">{score:.0%}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(min(max(score, 0.0), 1.0))
def render_skills(profile: CandidateProfile) -> None:
    """Skills as rounded pill tags, sorted by confidence (highest first)."""

    st.markdown('<div class="cf-section-title">Skills</div>', unsafe_allow_html=True)

    if not profile.skills:
        st.markdown('<span class="cf-muted">No skills detected.</span>', unsafe_allow_html=True)
        return

    sorted_skills = sorted(profile.skills, key=lambda s: s.confidence, reverse=True)

    tags_html = "".join(
        f'<span class="cf-skill-tag">{skill.name}</span>' for skill in sorted_skills
    )
    st.markdown(f'<div>{tags_html}</div>', unsafe_allow_html=True)    
def render_experience(profile: CandidateProfile) -> None:
    """One expander per experience entry, title/company visible when collapsed."""

    st.markdown('<div class="cf-section-title">Experience</div>', unsafe_allow_html=True)

    if not profile.experience:
        st.markdown('<span class="cf-muted">No experience entries found.</span>', unsafe_allow_html=True)
        return

    for entry in profile.experience:
        title = entry.title or "Unknown Role"
        company = entry.company or "Unknown Company"
        start = entry.start_date or "—"
        end = entry.end_date or "Present"

        with st.expander(f"{title}  ·  {company}  ({start} – {end})"):
            if entry.location:
                st.markdown(f'<span class="cf-muted">📍 {entry.location}</span>', unsafe_allow_html=True)
            if entry.description:
                st.write(entry.description)
            elif not entry.location:
                st.markdown('<span class="cf-muted">No further details available.</span>', unsafe_allow_html=True)


def render_education(profile: CandidateProfile) -> None:
    """One expander per education entry, degree/institution visible when collapsed."""

    st.markdown('<div class="cf-section-title">Education</div>', unsafe_allow_html=True)

    if not profile.education:
        st.markdown('<span class="cf-muted">No education entries found.</span>', unsafe_allow_html=True)
        return

    for entry in profile.education:
        degree = entry.degree or "Unknown Degree"
        institution = entry.institution or "Unknown Institution"
        start = entry.start_date or "—"
        end = entry.end_date or "—"

        with st.expander(f"{degree}  ·  {institution}  ({start} – {end})"):
            if entry.field_of_study:
                st.markdown(f"**Field of study:** {entry.field_of_study}")
            if entry.gpa is not None:
                st.markdown(f"**GPA:** {entry.gpa}")
            if not entry.field_of_study and entry.gpa is None:
                st.markdown('<span class="cf-muted">No further details available.</span>', unsafe_allow_html=True)    
def render_github_info(profile: CandidateProfile, sources_used: list) -> None:
    """
    GitHub section. CandidateProfile has no dedicated `github` object, so
    this surfaces what's actually available: the GitHub link (if merged
    in) and whether a GitHub source was used in this run.
    """
    st.markdown('<div class="cf-section-title">GitHub Information</div>', unsafe_allow_html=True)

    github_links = [link for link in profile.links if (link.label or "").lower() == "github"]
    github_used = any(src.startswith("github:") for src in sources_used)

    if not github_links and not github_used:
        st.markdown(
            '<span class="cf-muted">No GitHub source was used for this profile.</span>',
            unsafe_allow_html=True,
        )
        return

    if github_used:
        github_source = next((s for s in sources_used if s.startswith("github:")), None)
        username = github_source.split(":", 1)[1] if github_source else None
        if username:
            st.markdown(f"**GitHub username:** `{username}`")

    for link in github_links:
        st.markdown(f"🔗 [{link.url}]({link.url})")

    if not github_links:
        st.markdown(
            '<span class="cf-muted">GitHub data contributed to this profile, '
            'but no public profile link was captured.</span>',
            unsafe_allow_html=True,
        )


def render_sources_used(sources_used: list) -> None:
    """Pills showing which sources successfully contributed to this profile."""

    st.markdown('<div class="cf-section-title">Sources Used</div>', unsafe_allow_html=True)

    if not sources_used:
        st.markdown('<span class="cf-muted">No sources recorded.</span>', unsafe_allow_html=True)
        return

    pills_html = "".join(
        f'<span class="cf-pill-success" style="margin-right:0.4rem;">{src}</span>'
        for src in sources_used
    )
    st.markdown(f"<div>{pills_html}</div>", unsafe_allow_html=True)


def render_validation_warnings(warnings: list) -> None:
    """Validation/parse warnings, tucked into a collapsed expander."""

    label = f"⚠️ Validation Warnings ({len(warnings)})" if warnings else "✅ Validation Warnings (none)"

    with st.expander(label, expanded=False):
        if not warnings:
            st.markdown('<span class="cf-muted">No warnings were raised during this run.</span>', unsafe_allow_html=True)
        else:
            for w in warnings:
                st.markdown(f'<span class="cf-pill-warning">⚠</span>&nbsp; {w}', unsafe_allow_html=True)                


from pathlib import Path


def render_downloads(candidate_json_path, report_json_path) -> None:
    """
    Download buttons for the two files run_pipeline() already wrote to
    disk. We read them back as bytes rather than re-serializing the
    profile ourselves, so the download is byte-identical to what the
    backend produced.
    """
    st.markdown('<div class="cf-section-title">Downloads</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    candidate_path = Path(candidate_json_path)
    report_path = Path(report_json_path)

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
            st.markdown('<span class="cf-muted">candidate.json not found.</span>', unsafe_allow_html=True)

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
            st.markdown('<span class="cf-muted">pipeline_report.json not found.</span>', unsafe_allow_html=True)