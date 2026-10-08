# AI agent validation

| Agent / path | Initialization | Prompt / contract | Model / data | Tools / integration | Result |
|---|---|---|---|---|---|
| `RegInsightChatAgent` (`/api/chatbot/stream`) | PASS | PASS; JSON answer, known citations, numeric checks | Local Ollama `reginsight-chat:qwen3-1.7b`; curated references or calculated D1 | PASS; evidence event precedes answer, evidence-only fallback | PASS; two live local questions returned `local_llm` |
| `InspectionAgent` (`/api/agent/query`) | PASS | PASS; typed question and scope | Deterministic services; optional observation classifier | PASS; portfolio tools traced and evidence saved | PASS in 192-test suite |
| `observation_investigator` | PASS | PASS; rule-based intent and typed observation tools | Completed observation snapshot | PASS; tags, groups, recurrence, similarity and review paths | PASS in 192-test suite |
| `Classifier` (`/api/observations/classify`) | PASS | PASS; strict Pydantic evidence quote/rationale | Rules, mock, OpenAI, Claude, local, Ollama, Gemini adapters | PASS; bounded requests and fallback chain | PASS; live Ollama transport was unavailable, so the observed result fell back to rules |
| Earlier workspace Claude batch | PASS | PASS; rubric/evidence quote validation | Explicit Claude Sonnet configuration only | PASS; no silent rules-as-Claude success | BLOCKED — no Claude credential intentionally used |

The executable registry contains 15 tools. The public discovery endpoint now derives its schemas from that registry, preventing the previous omission of `get_semantic_groups` and `get_review_observations`.

## Live evidence

The local Ollama chat model was available and returned validated answers for “What does OAI mean?” and “What is the OAI rate?”. The first live request took about 14–32 seconds across runs; the calculated-rate answer took about 11–14 seconds. Observation classification against Ollama was attempted once; the provider transport was unavailable within the configured budget and the code returned a validated deterministic fallback. No paid remote provider was called.

## Boundaries

Provider adapters are contract-tested with doubles. Gemini/OpenAI/Claude live transport, production identity integration, and a real external vector service remain unverified. A rules fallback is reported as fallback and is never marked as a successful remote-model result.
