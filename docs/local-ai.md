# Keyless local AI with Ollama

The application uses Ollama with `qwen3:1.7b` for observation interpretation. OpenCode is a separate developer coding agent, not an inference service. The linked OpenCode documentation describes using Ollama as its model provider; this project connects directly to that same local runtime.

Choice: Qwen3 1.7B (approximately 1.4 GB download, Apache 2.0 model license). The initially proposed Qwen3.5 4B failed to load with an out-of-memory error on this approximately 12 GB RAM / Intel UHD machine and was removed. The smaller text model passed a live adapter test. This smoke test does not establish regulatory accuracy.

## Install and run

From the project folder:

```powershell
.\scripts\setup-ollama.ps1
.\scripts\start-real.ps1
```

Setup requires at least 12 GB free on the system drive for installation, model storage and working space. It downloads the official Windows installer, checks its Authenticode signature, installs Ollama, and pulls the model. There is no account or API key requirement. Downloads require internet; inference uses loopback only. No user files are deleted to make room.

Installation completed on 2026-09-20 after the user freed disk space. Ollama 0.34.2 and Qwen3 1.7B are installed. A live test of "Laboratory audit trails were disabled and original test results were deleted." returned Data Integrity / High in 12.0 seconds, with an exact evidence quote and source OllamaProvider, without fallback. Existing classification records are retained and are not relabeled as AI output. Restart the application to load the new environment settings.

`start-real.ps1` selects `AI_PROVIDER=ollama`, `AI_MODEL=qwen3:1.7b`, `AI_ENABLE_REMOTE=false`, and `OLLAMA_BASE_URL=http://127.0.0.1:11434`. It starts the installed service when needed and checks the model exists. If unavailable, the console warns and observation responses explicitly report keyword fallback. This script sets process environment variables; copying `.env.example` alone does not configure this launcher.

## Scope and validation

The AI Agent's observation interpretation and Observation analysis lab call the new Ollama provider. The all-source Classifier also accepts `provider='ollama'`. Risk arithmetic, company lookup, trends, datasets and existing saved tags remain deterministic. The separate synthetic Observation Workspace's rules demo remains a rules demonstration.

Requests use an 8192-token context, JSON schema, non-streaming responses, disabled thinking and a 300-second local timeout. Responses still pass the existing schema and exact evidence-quote checks. Invalid/truncated responses fall back to clearly identified rules. No API key is sent, including when older key variables exist in the terminal. The adapter rejects non-loopback origins and cloud model tags.

No OpenCode dependency is installed in the web application. OpenCode's recommended 64k+ context is for repository coding sessions and is unnecessary for bounded observation classification on this machine.

References: [OpenCode integration](https://docs.ollama.com/integrations/opencode), [model details](https://ollama.com/library/qwen3:1.7b), [Ollama Windows](https://docs.ollama.com/windows), [chat API](https://docs.ollama.com/api/chat).
