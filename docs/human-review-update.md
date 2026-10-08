# Human Review workflow update

Removed the Guided Investigation / Inspection intelligence assistant UI component from the Evidence workspace. The portfolio AI chatbot and graph analytics remain available.

Evidence and the existing Human Review form are now the last main workspace section. Data foundation and context sections appear before them. Approve / Modify / Reject, reviewer rationale, original assessments and append-only review history are unchanged. SQLite and existing data are preserved. Backend investigation APIs are retained for compatibility; this change removes the pictured UI module.

Updated architecture: architecture-human-review.png.

Validation:
- Vite production build passed; rebuilt frontend/dist is included.
- Existing tests/test_website_workspace.py: 4 passed.
- Chrome browser smoke: Guided Investigation absent, Evidence/Human Review last main section, no JavaScript errors. This layout check used API error responses; review persistence is covered by the backend tests.

Run using the existing project launch instructions. node_modules and local test caches are not included.
