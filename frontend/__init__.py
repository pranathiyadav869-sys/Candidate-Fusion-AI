# frontend/__init__.py
"""
CandidateFusion AI — Streamlit frontend package.

This package contains ONLY presentation-layer code: UI components,
styling, and a thin client wrapper around engine.projector.run_pipeline().

No business logic (parsing, merging, scoring, validation) lives here —
that all stays in engine/ and parsers/, untouched.
"""