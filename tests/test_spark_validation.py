import os
import sys
import pandas as pd
import pytest
from data_engineering.pipeline import transform

@pytest.fixture(scope='module')
def spark(tmp_path_factory):
    from pyspark.sql import SparkSession
    os.environ['PYSPARK_PYTHON']=sys.executable
    os.environ.setdefault('SPARK_LOCAL_IP','127.0.0.1')
    s=SparkSession.builder.master('local[2]').appName('ETLTests').config('spark.ui.enabled','false').config('spark.sql.shuffle.partitions','2').config('spark.local.dir',str(tmp_path_factory.mktemp('spark-local'))).getOrCreate()
    s.sparkContext.setLogLevel('ERROR')
    yield s
    s.stop()

def test_nullable_and_invalid_fields(spark):
    df=pd.DataFrame([
        {'inspection_id':'1','company_name':'  Example   Company ','inspection_date':'01/15/2024','classification':'official action indicated','observation_count':'2.0','citation_flag':'yes'},
        {'inspection_id':'2','company_name':'Example','inspection_date':'bogus','observation_count':'bad'},
        {'inspection_id':'3','company_name':'Example','inspection_date':'2030-01-01'},
        {'inspection_id':'4','company_name':'Example','observation_count':'-1'},
        {'inspection_id':'5','company_name':'Example','classification':'pending'},
    ]).fillna('')
    valid,rejected,duplicates,q=transform(spark,df,{},'2026-09-10')
    records={r.inspection_id:r.asDict() for r in valid.collect()}
    assert q['valid_records']==2 and q['rejected_records']==3
    assert records['1']['classification']=='OAI'
    assert records['1']['company_name']=='Example Company'
    assert records['5']['classification'] is None
    assert records['5']['citation_indicator'] is None
    assert records['5']['inspection_date'] is None
    assert q['invalid_dates']==1 and q['unknown_classifications']==1

def test_mapping_contract(spark):
    with pytest.raises(ValueError,match='identity'):
        transform(spark,pd.DataFrame([{'x':'value'}]),{},'2026-09-10')
