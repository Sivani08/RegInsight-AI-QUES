# RegInsight AI website

The application entry point now opens the RegInsight AI website and working inspection workspace. It preserves the supplied Agilisium logo and uses self-hosted IBM Plex Sans under the included Open Font License.

## Run with existing data

The built frontend is included. Use the existing Python environment or install `requirements.txt` into a Python 3.12 virtual environment. From the project root:

```powershell
./scripts/start-reginsight.ps1 -Python .venv/Scripts/python.exe -DatabaseUrl 'sqlite:///C:/absolute/path/inspections.db' -ObservationDatabase 'C:/absolute/path/intelligence.db' -Port 8000
```

Open http://127.0.0.1:8000. The two databases have different roles: the inspection store provides portfolio risk, while the observation corpus provides classification, source text, recurrence and review records. Keep them from the intended data release; the interface labels their scopes separately.

For PostgreSQL, pass the existing configured SQLAlchemy connection URL as `DatabaseUrl`. The observation corpus remains the existing SQLite intelligence store. Never place database credentials in frontend files.

## Build or change the frontend

```powershell
cd frontend
npm ci
npm run build
```

The active entry point imports `src/reginsight/RegInsight.jsx`. Older frontend modules remain in source for reference, but are not imported into the delivered website. No Lucide or other icon library is included in this website's bundle.

## Data initialization

The portable source archive excludes large databases and imported real workbooks. It includes the pre-existing, explicitly synthetic processed fixtures. To use those locally, load the inspection database with `python scripts/bootstrap.py` and build a rules-only observation snapshot with:

```powershell
python -m data_engineering.tag_observations --dataset synthetic,demo --provider rules --max-requests 0
```

Then select the clearly labeled synthetic dataset in the Observations tab. Real data is never silently replaced with demonstration records. Use the repository's existing source-import workflow for real inspection data.

On the first request for a completed snapshot, the website builds a narrow derived browsing index. On the supplied 280k-observation corpus this one-time preparation took about 109 seconds on this machine. Subsequent indexed observation pages took about 0.56 seconds; a company/text search took about 6.1 seconds. Timing depends on hardware and query scope. The original source and machine classifications remain unchanged.

## Implemented interactions

- Server-side search over company, site, inspection ID and observation text.
- Dataset, year, severity and theme filters; deterministic sorting and pagination across the whole filtered result.
- Record selection with original observation, evidence quote, provenance, classification rationale and related-record retrieval.
- Separate analytical severity and portfolio risk charts with descriptions and accessible trend data.
- Append-only Approve, Modify and Reject decisions with required reviewer/rationale, timestamp, original assessment and revision conflict checks.
- Tool-based natural-language investigations with persisted evidence links and source-reference buttons.
- Responsive navigation, functional search shortcut, keyboard-operable tabs, native modal focus handling and explicit empty/error states.

## Deployment boundaries

This is a working local website, not a formally validated regulatory system. Organization authentication is not configured. Review names are self-reported local identities, not authenticated signatures. Contact and policy destinations explicitly say that their content has not been supplied. Production identity, authorization, approved policy content, backup/retention and validation are deployment requirements; the UI makes no compliance claim.

No remote model request is made on page load. Existing provider configuration and explicit AI-enablement gates remain in effect. Rules-derived classifications are visibly labeled.

## Validation

The frontend production build passed. Thirty-five tests covering website browsing/reviews, existing APIs, intelligence integration and cache behavior passed; an additional access-log redaction regression test passed after fixing structured Uvicorn logging. Updated website tests also verify literal search, unknown-run rejection and review preservation.

Browser checks covered desktop, narrow/mobile layouts, actual source record selection, search, sorting, source traceability, the evidence-backed assistant and the sign-in placeholder. Backend review tests use isolated fixtures rather than adding artificial reviewer decisions to real inspection records.

## Prohibited-pattern audit

| Brief restriction | Delivered treatment |
| --- | --- |
| 1. Harsh / oversized gradients | No gradients |
| 2. Lucide / generic icon libraries | No icon-library imports in the active entry point |
| 3. Pricing cards | No pricing content |
| 4. Pure-white backgrounds | Ivory, neutral and graphite surfaces; original logo blended onto ivory |
| 5. Decorative multicolor UI | Steel-blue accent; amber, red and green only for semantic states |
| 6. Fake demonstrations | Backend-driven source data; explicitly labeled synthetic scopes are opt-in |
| 7. Checkmark bullets | No checkmark lists |
| 8. Excessive pill radius | Square analytical surfaces; 3px control corners |
| 9. Purple / black identity | Graphite, ivory and steel-blue |
| 10. Three identical feature cards | Editorial sections, analytical regions and prose columns without cards |
| 11. Emoji | None |
| 12. Skeleton loaders | Plain loading status text |
| 13. Glowing orbs | None |
| 14. Liquid glass | None |
| 15. Dot grids | None |
| 16. Em dashes | None in authored active UI copy |
| 17. Prohibited fonts | Self-hosted IBM Plex Sans |
| 18. Sparkles | None |
| 19. Animated arrows | Static directional labels only |
| 20. Colored left stripes | None; selection uses a surface and bottom tab rule |
| 21. Fake testimonials | None |
| 22. Bento layouts | Sequential analytical workspace and editorial sections |
| 23. Terminal hero | Real chart, metrics, observations and evidence panel |
| 24. Neon | Muted palette |
| 25. Contrastive marketing construction | Direct product copy |
| 26. Pastel SaaS styling | Institutional neutral surfaces and compact typography |
| 27. Excessive hover motion | No hover animations |
| 28. Fabricated trust claims | Actual logo and query-derived metrics; regulatory context qualified |
| 29. Stock AI imagery | No illustrative photography or generated imagery |
| 30. Rounded cards everywhere | Tables, dividers, process rows, analytical surfaces and source text |
