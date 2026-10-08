import json
import pytest
from backend.genai.providers import OllamaProvider, analyze_observation
from backend.genai.classifier import Classifier


def test_keyless_schema_request_and_verified_response(monkeypatch):
    monkeypatch.delenv('AI_MODEL', raising=False)
    monkeypatch.setenv('AI_API_KEY', 'must-never-be-forwarded')
    monkeypatch.setenv('AI_ENABLE_REMOTE', 'false')
    provider = OllamaProvider()
    def request(url, payload, headers, timeout, local=False):
        assert url == 'http://127.0.0.1:11434/api/chat'
        assert headers == {} and local is True and timeout == 300
        assert payload['model'] == 'qwen3:1.7b'
        assert payload['think'] is False and payload['stream'] is False
        assert 'reason' in payload['format']['properties']
        return {'done': True, 'message': {'content': json.dumps({
            'category': 'Quality and compliance', 'theme': 'CAPA',
            'severity': 'High', 'confidence': .8, 'reason': 'CAPA failed'})}}
    monkeypatch.setattr(provider.gate, 'request', request)
    result = analyze_observation('CAPA failed yesterday.', provider)
    assert result['source'] == 'OllamaProvider'
    assert result['evidence_quote'] == 'CAPA failed'
    assert not result.get('fallback')


@pytest.mark.parametrize('url', ['https://example.com','http://example.com','http://secret@localhost:11434','http://localhost:11434/api'])
def test_ollama_rejects_nonlocal_or_credential_urls(monkeypatch, url):
    monkeypatch.setenv('OLLAMA_BASE_URL', url)
    with pytest.raises(ValueError):
        OllamaProvider().analyze('CAPA failed')


def test_ollama_truncation_falls_back(monkeypatch):
    provider = OllamaProvider()
    monkeypatch.setattr(provider, 'request', lambda *args: {'done': True, 'done_reason': 'length'})
    assert analyze_observation('CAPA failed', provider)['fallback'] is True


def test_ollama_uses_intelligence_schema(monkeypatch):
    monkeypatch.delenv('AI_MODEL', raising=False)
    classifier = Classifier(provider='ollama')
    assert classifier.model == 'qwen3:1.7b'
    assert classifier.provider.structured is True
    assert 'evidence_quote' in classifier.provider.schema()['properties']


def test_cloud_model_rejected(monkeypatch):
    monkeypatch.setenv('AI_MODEL', 'qwen3.5:cloud')
    with pytest.raises(ValueError):
        OllamaProvider().analyze('CAPA failed')
