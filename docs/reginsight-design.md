# RegInsight AI design and implementation

## Reference lock

Direct build against the user's clinical-regulatory command center brief, with the existing source-linked inspection product as the functional target. The supplied brief supersedes the earlier teal/white style reference. No live Refero MCP was available; Refero's bundled typography, anti-pattern and interaction guidance informed the implementation.

| Decision | Source | Application |
| --- | --- | --- |
| Warm neutral canvas, graphite structure, steel-blue selection | User brief | Ivory surfaces, thin rules, no gradients or pure-white interface backgrounds |
| IBM Plex Sans, compact technical metadata | Refero typography reference and user font restrictions | One professional family, tabular numerals, restrained 44px maximum display type |
| A working evidence console dominates the first screen | User hero and traceability requirements | Real API metrics, selected source text and provenance; no illustrative fake dashboard |
| Table and persistent evidence pane | Existing observation intelligence data model | Search/sort/filter on the server; explicit missing dates and unavailable risk scores |
| Numbered process narrative and architecture rows | User workflow and architecture brief | Dividers and typographic hierarchy instead of feature-card grids |
| Controlled review | Existing immutable snapshots and user human-review requirement | Append-only decisions, reviewer note, timestamp and optimistic revision checks; machine classification preserved |
| Exact Agilisium asset | Previous explicit user request | Original image, with white margins clipped in CSS and multiply blending onto ivory |

No stock or generated imagery is needed: charts, source text and structured evidence are the media. Semantic amber/red/green appear only for meaningful states. Corners are square or 3px. No icon libraries are used by the new interface.

## Operational boundaries

The UI uses the existing local backend and corpus. It makes no remote AI calls on page load. Assistant answers use existing tool routing and cite returned evidence. Unavailable services produce retryable errors, not fabricated records. Sign-in, contact and legal policies explicitly report that configuration/content is not supplied. Local reviewer names are self-reported and are not authenticated signatures; deployment identity and access controls remain an integration requirement.
