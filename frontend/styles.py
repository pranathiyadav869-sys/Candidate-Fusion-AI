# frontend/styles.py
"""
Custom CSS theme for CandidateFusion AI.

Streamlit's config.toml (.streamlit/config.toml) handles native widget
theming (buttons, progress bars, inputs). This module covers everything
config.toml can't reach: cards, skill tag pills, section headers, and
overall spacing — used by the display components we'll build in later
steps (Steps 6-9).

apply_custom_theme() is called once, right after st.set_page_config(),
and injects CSS via st.markdown(). No business logic lives here.
"""

import streamlit as st

# Single source of truth for the palette, so every future component
# pulls from the same values instead of hardcoding hex codes.
COLORS = {
    "primary": "#2563EB",      # blue — buttons, links, accents
    "primary_light": "#DBEAFE",  # light blue — tag backgrounds
    "background": "#F8FAFC",   # page background — light gray
    "surface": "#FFFFFF",      # card background — white
    "border": "#E2E8F0",       # light gray borders
    "text": "#1E293B",         # near-black body text
    "text_muted": "#64748B",   # secondary/gray text
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
}


def apply_custom_theme() -> None:
    """Inject the CandidateFusion AI CSS theme into the current page."""
    st.markdown(
        f"""
        <style>
        /* ---------- Global spacing & typography ---------- */
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1100px;
        }}
        h1, h2, h3 {{
            color: {COLORS["text"]};
            font-weight: 700;
        }}
        p, label, span {{
            color: {COLORS["text"]};
        }}

        /* ---------- Section header ---------- */
        .cf-section-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: {COLORS["text"]};
            margin-top: 1.5rem;
            margin-bottom: 0.6rem;
            padding-bottom: 0.4rem;
            border-bottom: 2px solid {COLORS["primary_light"]};
        }}

        /* ---------- Card container ---------- */
        .cf-card {{
            background-color: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 1.1rem 1.3rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }}
        .cf-card-title {{
            font-weight: 700;
            font-size: 1rem;
            color: {COLORS["text"]};
            margin-bottom: 0.15rem;
        }}
        .cf-card-subtitle {{
            font-size: 0.88rem;
            color: {COLORS["text_muted"]};
            margin-bottom: 0.4rem;
        }}

        /* ---------- Skill tags ---------- */
        .cf-skill-tag {{
            display: inline-block;
            background-color: {COLORS["primary_light"]};
            color: {COLORS["primary"]};
            font-size: 0.82rem;
            font-weight: 600;
            padding: 0.3rem 0.75rem;
            border-radius: 999px;
            margin: 0 0.35rem 0.35rem 0;
        }}

        /* ---------- Misc helpers ---------- */
        .cf-muted {{
            color: {COLORS["text_muted"]};
            font-size: 0.85rem;
        }}
        .cf-pill-success {{
            background-color: #DCFCE7;
            color: {COLORS["success"]};
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .cf-pill-warning {{
            background-color: #FEF3C7;
            color: {COLORS["warning"]};
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }}

        /* ---------- Buttons ---------- */
        div.stButton > button {{
            border-radius: 8px;
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )