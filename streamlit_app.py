"""
CandidateFusion AI — Streamlit entry point.

Run with:
    streamlit run streamlit_app.py

This file only collects inputs, calls frontend.pipeline_client, and
displays the result. All pipeline logic lives in engine/ and parsers/,
unmodified.
"""
import streamlit as st
from frontend.pipeline_client import generate_candidate_profile
from frontend.styles import apply_custom_theme
from frontend.ui_components import (
    render_identity_header,
    render_skills,
    render_experience,
    render_education,
    render_github_info,
    render_sources_used,
    render_validation_warnings,
    render_downloads,
)
# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CandidateFusion AI",
    page_icon="🧩",
    layout="wide",
)
apply_custom_theme()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
# pipeline_result: holds the PipelineClientResult from the last run so it
#   survives Streamlit re-runs (e.g. when expanders are toggled).
# uploader_version: bumped on Reset to force file_uploader widgets to
#   remount empty, since they don't clear themselves otherwise.
st.session_state.setdefault("pipeline_result", None)
st.session_state.setdefault("uploader_version", 0)

v = st.session_state["uploader_version"]

# ---------------------------------------------------------------------------
# Sidebar — input collection
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Candidate Sources")
    st.caption("Provide at least one source below.")

    resume_file = st.file_uploader(
        "Resume (PDF)", type=["pdf"], key=f"resume_{v}"
    )
    ats_file = st.file_uploader(
        "ATS JSON (optional)", type=["json"], key=f"ats_{v}"
    )
    csv_file = st.file_uploader(
        "Recruiter CSV (optional)", type=["csv"], key=f"csv_{v}"
    )
    github_input = st.text_input(
        "GitHub username or profile URL (optional)",
        placeholder="octocat  or  https://github.com/octocat",
        key=f"github_{v}",
    )

    st.divider()
    col1, col2 = st.columns(2)
    generate_clicked = col1.button(
        "Generate Candidate Profile", type="primary", use_container_width=True
    )
    reset_clicked = col2.button("Reset", use_container_width=True)

# ---------------------------------------------------------------------------
# Reset handling
# ---------------------------------------------------------------------------
if reset_clicked:
    st.session_state["pipeline_result"] = None
    st.session_state["uploader_version"] += 1
    st.rerun()

# ---------------------------------------------------------------------------
# Generate handling
# ---------------------------------------------------------------------------
if generate_clicked:
    if not any([resume_file, ats_file, csv_file, github_input]):
        st.sidebar.warning(
            "Please provide at least one source before generating a profile."
        )
    else:
        with st.spinner("Generating candidate profile…"):
            client_result = generate_candidate_profile(
                resume_file=resume_file,
                ats_file=ats_file,
                csv_file=csv_file,
                github_input=github_input,
            )
        st.session_state["pipeline_result"] = client_result

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
st.title("🧩 CandidateFusion AI")
st.caption("Upload candidate sources on the left, then generate a fused profile.")

result_state = st.session_state["pipeline_result"]

if result_state is None:
    st.info("No profile generated yet. Fill in the sidebar and click **Generate Candidate Profile**.")

elif not result_state.success:
    st.error(result_state.error_message)

else:
    pipeline_result = result_state.result  # a PipelineResult
    st.success(
        f"Profile generated in {pipeline_result.elapsed_seconds:.2f}s "
        f"using sources: {', '.join(pipeline_result.sources_used) or '—'}"
    )

    if pipeline_result.warnings:
        st.warning(f"{len(pipeline_result.warnings)} warning(s) were raised — see below.")

    # === Step 6: identity header + confidence bar goes here ===
    render_identity_header(pipeline_result.profile)
    # === Step 7: skills tags go here ===
    render_skills(pipeline_result.profile)
    # === Step 8: experience / education expanders go here ===
    render_experience(pipeline_result.profile)
    render_education(pipeline_result.profile)
    # === Step 9: GitHub info + sources used + validation warnings go here ===
    render_github_info(pipeline_result.profile, pipeline_result.sources_used)
    render_sources_used(pipeline_result.sources_used)
    render_validation_warnings(pipeline_result.warnings)
    # === Step 10: download buttons go here ===
    render_downloads(pipeline_result.candidate_json_path, pipeline_result.report_json_path)
    