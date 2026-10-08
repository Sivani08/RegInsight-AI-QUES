# Optional free-provider assessment

Checked against official documentation on 2026-09-18. No credentialed API request was made. Availability and quotas can change; an account's displayed limits are authoritative.

The optional adapter selected is **Google Gemini**, default model **gemini-2.5-flash-lite**. It is suitable for short classification/extraction with structured output, has documented Indian availability, and retains a standard free tier. Selection is based on documented capability and integration fit, not a comparative accuracy or speed benchmark. Other/newer models are configurable; newest is not automatically most suitable for this bounded extraction task.

| Criterion | Gemini 2.5 Flash-Lite | Groq alternative |
|---|---|---|
| Free developer quota | Standard input/output currently listed free; exact account quota varies | Free plan with model-specific limits |
| Requests/minute | Read actual project limits in AI Studio; no universal allowance promised here | Published example gpt-oss-20b: 30 RPM; account overrides possible |
| Requests/day | Project/model-specific; verify AI Studio | Published example gpt-oss-20b: 1000 RPD |
| Token limits | Project-specific TPM; client uses conservative estimates and handles 429 | Example gpt-oss-20b: 8000 TPM, 200000 TPD |
| Structured JSON | Supported | Supported on selected models |
| JSON schema | Supported subset; local Pydantic still authoritative | Strict schema support documented for selected models including GPT-OSS |
| Context window | 1048576 input; 65536 output tokens documented | Model-specific; not independently verified in this assessment |
| Reliability | No free-tier capacity guarantee; retries/fallback implemented | No comparative live reliability benchmark performed |
| Python/httpx | REST JSON adapter implemented, simulated responses tested | REST integration feasible; no Groq adapter added in this change |
| India | Explicitly listed among supported regions | No definitive India-specific availability confirmation obtained |
| Credit card | Free/new-account tier documented; no account signup was performed, so exact signup/card requirements are unverified | Billing FAQ requires a payment method for Developer upgrade; free signup not exercised |
| Development usability | Suitable for bounded trials, not guaranteed to classify 22027 unique texts in one free run | Potentially useful for trials; published quotas constrain full-corpus throughput |
| Terms | Professional/business development allowed subject to API terms and regional/age conditions; unpaid data-use terms apply | Terms/account eligibility must be checked before choosing it; not fully evaluated for deployment here |

Sources: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [model specification](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [regions](https://ai.google.dev/gemini-api/docs/available-regions), [billing](https://ai.google.dev/gemini-api/docs/billing), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [API terms](https://ai.google.dev/gemini-api/terms), [Groq limits](https://console.groq.com/docs/rate-limits), [Groq structured output](https://console.groq.com/docs/structured-outputs), [Groq billing](https://console.groq.com/docs/billing-faqs).

Free does not mean unlimited or private. Google's unpaid-service content can be used to improve products under its terms. Review those terms before transmitting inspection text. The supplied public-style dataset does not establish permission to upload future confidential company records. No source data was sent remotely during validation.

The application does not select a billing tier or inspect an account's balance. Using `--enable-ai` on a paid account can incur charges. Keep remote access off for zero-request operation. This delivery uses standard requests, not Google's paid Batch API, paid embeddings, search grounding or context caching. Per-run budgets include retries, and unsuccessful/disabled requests leave explicit rule fallbacks.

The default local grouping has zero API cost and requires no extra model. Optional [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) supplies lightweight 384-dimensional embeddings when installed locally; its dependency/model footprint and accuracy were not benchmarked on this machine.
