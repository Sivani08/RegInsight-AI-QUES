import pytest
from data_engineering.pipeline import read_source
from data_engineering.sample import generate

def test_synthetic_reproducible(tmp_path):
    a=tmp_path/'a.csv'; b=tmp_path/'b.csv'
    assert generate(a)>200
    generate(b)
    assert a.read_bytes()==b.read_bytes()
    df=read_source(a)
    assert set(df['Classification'])=={'NAI','VAI','OAI','PENDING'}
    assert df.duplicated().sum()==1

def test_bad_input(tmp_path):
    with pytest.raises(ValueError,match='not found'): read_source(tmp_path/'missing.csv')
    p=tmp_path/'bad.xlsx'; p.write_text('invalid')
    with pytest.raises(ValueError,match='Cannot read'): read_source(p)

def test_excel_and_parquet_input(tmp_path):
    import pandas as pd
    source=pd.DataFrame([{'Company':'Example','FEI':'0000123','Count':'0'}])
    for suffix in ['.xlsx','.parquet']:
        path=tmp_path/f'input{suffix}'
        if suffix=='.xlsx': source.to_excel(path,index=False)
        else: source.to_parquet(path,index=False)
        assert read_source(path).iloc[0]['FEI']=='0000123'
