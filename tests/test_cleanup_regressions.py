"""Regressions for discovery and portable configuration; no provider requests."""
import json
import pytest
from backend.api.agent import tools
from backend.tools.observation_tools import ObservationTools
from data_engineering.dataset_inventory import source_paths

def test_tool_discovery_matches_executable_registry():
    registry=ObservationTools(None).registry
    assert set(tools())==set(registry)
    assert {'get_semantic_groups','get_review_observations'} <= set(tools())
    for name,(schema,_) in registry.items():
        assert tools()[name]==schema.model_json_schema()

def test_manifest_paths_are_project_relative(tmp_path,monkeypatch):
    (tmp_path/'config').mkdir()
    absolute=tmp_path/'external.xlsx'
    (tmp_path/'config/dataset_sources.json').write_text(json.dumps({'workbooks':['data/raw/example.xlsx',str(absolute)]}))
    elsewhere=tmp_path/'elsewhere';elsewhere.mkdir();monkeypatch.chdir(elsewhere)
    assert source_paths(tmp_path)==[tmp_path/'data/raw/example.xlsx',absolute]

def test_optional_source_manifest_can_be_absent(tmp_path):
    assert source_paths(tmp_path)==[]

def test_benchmarks_never_attach_to_a_different_dataset(tmp_path,monkeypatch):
    from pg_client import TestClient
    from backend.api.main import create_app
    from backend.database.postgres import connection
    from backend.database.store import Store
    from backend.database.load import load
    with connection() as current:
        current.execute("INSERT INTO staging.annual_metadata(id,dataset_id,payload) VALUES (1,'different-dataset','{}')")
    store=Store();load(store=store)
    with TestClient(create_app(store)) as client:
        response=client.get('/api/benchmarks')
        assert response.status_code==200 and response.json()['available'] is False

def test_all_fifteen_tools_execute_against_isolated_evidence(tmp_path,monkeypatch):
    from data_engineering.intelligence_sources import ingest,db
    from backend.services import observation_intelligence as service
    from backend.database.store import Store
    from backend.database.load import load
    from backend.services.intelligence import Intelligence
    path='intelligence';(tmp_path/'data').mkdir()
    ingest(tmp_path,path);run=service.run(path=path,provider='rules')
    oid=service.tags(path=path,limit=1).records[0].observation_id
    monkeypatch.setattr(service,'db',lambda *args,**kwargs:db(path))
    store=Store();load(store=store)
    store.save_evidence('fixture',{'records':[]})
    tools=ObservationTools(Intelligence(store))
    special={'analyze_observation':{'observation_text':'Original laboratory records were not retained after testing.'},
             'get_evidence':{'analysis_id':'fixture'},
             'find_similar_observations':{'observation_id':oid,'run_id':run['id']}}
    for name in tools.registry:
        assert tools.call(name,**special.get(name,{})) is not None
    assert len(tools.trace)==15 and all(t['status']=='complete' for t in tools.trace)

@pytest.mark.parametrize('name',['rules','mock','openai','claude','local','ollama','gemini'])
def test_provider_adapters_initialize_without_network(name):
    from backend.genai.classifier import Classifier
    classifier=Classifier(name,enable_ai=False,max_requests=0)
    assert classifier.name==name and classifier.gate.requests==0

