"""Run after ETL. Checks actual Spark output without repeatedly starting a JVM."""
import json
from pathlib import Path
import pandas as pd
import pytest

@pytest.mark.skipif(not Path('data/processed/quality.json').exists(),reason='Run Spark ETL first')
def test_spark_output():
    q=json.loads(Path('data/processed/quality.json').read_text(encoding='utf-8'))
    valid=pd.read_parquet('data/processed/inspections.parquet')
    assert q['engine']=='PySpark'
    assert q['total_records']==q['valid_records']+q['rejected_records']+q['duplicate_records']
    assert valid.inspection_id.is_unique
    assert not valid.rejection_reason.any()
    if q['data_label']=='SYNTHETIC DEMONSTRATION DATA':
        assert q['rejected_records']==1
        assert q['duplicate_records']==1
        assert q['unknown_classifications']==1
        assert valid.loc[valid.inspection_id=='SYN-UNKNOWN','classification'].isna().all()
        assert valid.loc[valid.inspection_id=='SYN-UNKNOWN','citation_indicator'].isna().all()
