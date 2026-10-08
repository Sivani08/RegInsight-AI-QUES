import pytest
from backend.database.store import Store

def test_atomic_replace_and_filters():
    store=Store()
    records=[{'inspection_id':'1','company_key':'example','company_name':'Example','site_name':'Example Site','site_key':'site-id','inspection_year':2024}]
    store.replace(records,{'valid_records':1})
    assert len(store.search(company='Example',year=2024))==1
    assert len(store.search(site='Example Site'))==1
    assert store.search(company="' OR 1=1 --")==[]
    with pytest.raises(ValueError): store.replace(records*2,{})
    assert len(store.search())==1
    store.save_evidence('abc',{'records':records})
    store.replace([],{'valid_records':0})
    assert store.get_evidence('abc')['records']==records
