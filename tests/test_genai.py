import pytest
from backend.genai.providers import analyze_observation,AIProvider,MockProvider

class Broken(AIProvider):
    def analyze(self,text): raise TimeoutError('secret-key must not escape')

class Fabricating(AIProvider):
    def analyze(self,text): return {'category':'Quality and compliance','theme':'CAPA','severity':'High','confidence':.8,'reason':'99 inspections prove risk'}

class Grounded(AIProvider):
    def analyze(self,text): return {'category':'Quality and compliance','theme':'CAPA','severity':'High','confidence':.8,'reason':'CAPA failed'}

def test_rules():
    r=analyze_observation('Repeated CAPA failure and audit trail disabled.',MockProvider())
    assert r['theme']=='Data Integrity' and r['severity']=='High' and r['source']=='rules'

def test_provider_failure_and_invented_evidence():
    for p in [Broken(),Fabricating()]:
        r=analyze_observation('CAPA failed',p)
        assert r['fallback'] and 'secret-key' not in str(r)
        assert '99 inspections' not in str(r)

def test_validated_provider():
    r=analyze_observation('CAPA failed yesterday.',Grounded())
    assert r['evidence_quote']=='CAPA failed' and r['source']=='Grounded'

def test_empty():
    with pytest.raises(ValueError): analyze_observation('   ')
