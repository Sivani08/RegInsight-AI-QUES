# Readability and graph-insight revision — 26 September 2026

Baseline: the user-supplied Desktop/RegInsight-AI-3D-Application.zip. Its frontend, backend and configuration files were compared against the working copy and matched exactly before editing. The revised archive preserves that ZIP's data files unchanged.

Changes:
- 3D animation starts automatically without a click. Pause remains available. A reduced-motion preference uses slower rotation and removes the vertical oscillation, as the user explicitly requested autoplay.
- Segoe UI/system sans typography replaces the previous display font on the new interface. Body text is 15–18 px, table text 14 px, metadata generally 12–13 px, with stronger headings, control labels and numerical values.
- Wider copilot, aligned chart headers, clearer table columns and responsive reflow.
- Each main graph has an authoritative backend-generated insight. The copilot uses the same summary for graph questions.
- Activity summaries identify partial years and compare only complete years in their explanatory text. Missing citation denominators remain unavailable. Classification shares and risk-band counts respect the dashboard filters.
- Distribution bars represent shares of their total. Trend lines join recorded yearly values with straight segments instead of smoothed interpolation.

Validation:
- 160 backend tests passed; 2 existing skips. Spark/JVM execution was not rerun.
- Production frontend build passed, with the existing Three.js bundle-size advisory.
- Desktop and mobile browser checks passed: animation changes before any interaction, pause works, autoplay also starts with reduced-motion enabled, no viewport overflow, no JavaScript page errors, four chart insight panels render, expected missing-citation explanation appears, table/KPI fonts are enlarged.
- Graph-summary tests cover empty scopes, tied classifications, missing dates/rates, partial-year handling and equality between dashboard and copilot headlines under different filters.

Run the revised version from a newly extracted folder using Start-RegInsight.cmd. Close the previous app server first if it already occupies port 8018. A browser refresh loads the new built assets.
