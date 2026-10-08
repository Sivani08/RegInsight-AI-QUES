# Feature-to-file traceability

| Feature | UI file | API | Service | Agent | Tool | Data source |
|---|---|---|---|---|---|---|
| Landing/access/login | experience/Experience.jsx | auth/status, login, logout | api/security.py | None | None | Process key / in-memory sessions |
| Portfolio cards/charts/filters | Experience.jsx | GET dashboard | Intelligence; dashboard_queries; graph_insights | None | Direct calculations | Inspection Store/marts |
| Graph analytics conversation | Experience.jsx:AnalyticsCopilot | POST agent/dashboard-query | DashboardInsights; semantic planner | Deterministic service | Direct SQL/risk methods | Store + observation snapshot by focus |
| Local AI chat | experience/Chatbot.jsx | POST chatbot/stream | DashboardInsights | RegInsightChatAgent | Direct retrieval, no LLM tools | chat_knowledge.json or calculated D1 |
| Evidence browse/search/sort/page | reginsight/RegInsight.jsx | workspace/summary, observations | workspace.cohort; website_index; retrieval_search | None | None | Completed observation run |
| Source panel / related records | reginsight/Evidence.jsx | observations/tags; observations/similar; workspace/observations | observation_intelligence | None | Same services as tools | Original text, provenance, group membership |
| Observation investigation | reginsight/Assistant.jsx | POST agent/query | observation_intelligence | InspectionAgent → investigate | ObservationTools | Snapshot + saved evidence |
| Human review/history | reginsight/Evidence.jsx | workspace/reviews | workspace.review/history | None | None | website_reviews |
| Company/site risk/trend/recurrence | Retained API; current copilot can use supported scopes | profile, risk, trends, recurrence | Intelligence; risk engine; metrics | InspectionAgent when invoked | Six portfolio tools | Canonical inspections |
| Text classification | Retained API | observations/analyze; observations/classify | Classifier; contracts; request gate | Model-backed classification service | analyze_observation | Supplied text + versioned cache |
| Batch tags/groups/severity | Retained API/CLI | observations/batch-tag, jobs, tags, groups, severity | observation_intelligence | Bounded Classifier | Nine observation tools | Normalized corpus |
| Annual industry benchmarks | Retained API | benchmarks | api/benchmarks.py | None | None | annual_benchmarks.json |
| Earlier 72-observation demo | Retained API; old UI removed as already unreachable | observation-workspace family | services/observations.py | Rules/Claude classifier | None | Synthetic demo + workspace DB |
| Clinical QC ingestion/signals | Retained API; no current navigation screen | qc/import, import-csv, signals, review, export | qc_data, qc_connections, qc_signals | None | Operator-configured HTTP import | QC records / separate SQLite |
| Supplied reference search | Retained API; explicit index build needed | qc/knowledge | knowledge.search | None | FTS5 search | PDF pages / PPTX slides |
| Data-quality diagnostics | Portfolio/copilot + retained API | data-quality; observations/quarantine | Store metadata; corpus | None | None | ETL quality/reject/conflict records |
| Site alerts | Retained API | alerts | analytics/alerts.py | None | None | Configured rules + inspections |

Paths in the UI column are relative to frontend/src. API paths are relative to /api. A retained backend capability is explicitly distinguished from a visible page; cleanup did not add navigation or expose previously unmounted screens.
