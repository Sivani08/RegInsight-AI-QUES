import logging,os,hashlib,json
from pydantic import ValidationError
from backend.analytics.intelligence_taxonomy import VERSION,normalize,rules
from backend.genai.contracts import Classification,ObservationTag
from backend.genai.providers import MockProvider,OpenAIProvider,ClaudeProvider,LocalProvider,OllamaProvider,GeminiProvider
from backend.genai.request_gate import RequestGate,RequestLimit
PROVIDERS={'rules':MockProvider,'mock':MockProvider,'openai':OpenAIProvider,'claude':ClaudeProvider,'local':LocalProvider,'ollama':OllamaProvider,'gemini':GeminiProvider}
DEFAULT_MODELS={'ollama':'qwen3:1.7b','gemini':'gemini-2.5-flash-lite','rules':'deterministic','mock':'deterministic'}
def cache_key(text,model,provider):
    from backend.genai.classification_prompt import PROMPT_VERSION
    digest=hashlib.sha256((normalize(text)+VERSION+PROMPT_VERSION+model).encode()).hexdigest()
    return provider+':'+digest

class Classifier:
    def __init__(self,provider='rules',model=None,enable_ai=None,max_requests=None,gate=None):
        if provider not in PROVIDERS:raise ValueError('Unsupported provider')
        self.name=provider;self.model='deterministic' if provider in ('rules','mock') else model or os.getenv('AI_MODEL') or DEFAULT_MODELS.get(provider,'unconfigured')
        self.gate=gate or RequestGate(enabled=enable_ai,max_requests=max_requests)
        self.provider=PROVIDERS[provider]()
        if provider not in ('rules','mock'):
            self.provider.model=self.model;self.provider.structured=True;self.provider.gate=self.gate
        self.failures=0;self.fallback_count=0
        from backend.genai.redaction import install_redaction
        install_redaction()
        self.local_fallback=None
        if provider=='gemini' and os.getenv('OLLAMA_FALLBACK_MODEL'):
            self.local_fallback=OllamaProvider();self.local_fallback.model=os.environ['OLLAMA_FALLBACK_MODEL']
            self.local_fallback.structured=True;self.local_fallback.gate=self.gate
    def classify(self,text):
        text=normalize(text)
        if not text:raise ValueError('Empty observation')
        from backend.genai.classification_prompt import PROMPT_VERSION
        context={'observation_text':text}
        if self.name in ('rules','mock'):
            parsed=Classification.model_validate(rules(text),context=context)
            return ObservationTag(**parsed.model_dump(),source=self.name,model='deterministic',ai_generated=False,prompt_version=PROMPT_VERSION)
        chain=[(self.name,self.model,self.provider)]
        if self.local_fallback:chain.append(('ollama',self.local_fallback.model,self.local_fallback))
        invalid=False
        for index,(source,model,provider) in enumerate(chain):
            try:
                if len(text)>int(os.getenv('AI_MAX_TEXT_LENGTH','12000')):break
                value=provider.analyze(text)
            except (json.JSONDecodeError,ValidationError):
                self.failures+=1;invalid=True;break
            except Exception as exc:
                if not isinstance(exc,RequestLimit):self.failures+=1
                continue
            try:parsed=Classification.model_validate(value,context=context)
            except (ValueError,TypeError):
                self.failures+=1;invalid=True;break
            if index:self.fallback_count+=1
            return ObservationTag(**parsed.model_dump(),source=source,model=model,prompt_version=PROMPT_VERSION,
                                  fallback=bool(index),raw_status='provider_fallback' if index else 'validated')
        self.fallback_count+=1
        if self.fallback_count<=3:logging.getLogger(__name__).warning('Observation classification using deterministic fallback')
        parsed=Classification.model_validate(rules(text),context=context)
        return ObservationTag(**parsed.model_dump(),source='rules',model='deterministic',ai_generated=False,
                              fallback=True,prompt_version=PROMPT_VERSION,raw_status='invalid_output' if invalid else 'provider_unavailable')
