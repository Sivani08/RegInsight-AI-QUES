# Tool registry

The route `/api/agent/tools` and `ObservationTools.registry` expose the same 15 executable contracts.

| Tool | Implementation | Purpose |
|---|---|---|
| `search_inspections` | `Tools.search_inspections` | Filter canonical inspection records |
| `calculate_risk` | `Tools.calculate_risk` | Existing deterministic risk score |
| `analyze_trend` | `Tools.analyze_trend` | Year history and cumulative risk trend |
| `find_recurring_risks` | `Tools.find_recurring_risks` | Keyword theme recurrence |
| `analyze_observation` | `providers.analyze_observation` | Strict single-text interpretation/fallback |
| `get_evidence` | `Tools.get_evidence` | Read saved analysis evidence |
| `get_observation_tags` | `observation_intelligence.tags` | Paged validated tags |
| `find_recurring_themes` | `observation_intelligence.metrics` | Theme recurrence aggregates |
| `get_theme_trend` | `observation_intelligence.metrics` | Year-grouped theme metrics |
| `get_severity_distribution` | `observation_intelligence.metrics` | Severity counts |
| `find_similar_observations` | `observation_intelligence.similar` | Same semantic group evidence |
| `get_company_observation_intelligence` | `observation_intelligence.metrics` | Company-scoped observation metrics |
| `get_site_observation_intelligence` | `observation_intelligence.metrics` | Site-scoped observation metrics |
| `get_semantic_groups` | `observation_intelligence.groups` | Group summary and representative IDs |
| `get_review_observations` | `observation_intelligence.tags` | Records still requiring review |

All calls use Pydantic schemas, append a running/complete/failed trace item and let the caller handle controlled exceptions. No tool accepts arbitrary SQL or a user-supplied external URL.
