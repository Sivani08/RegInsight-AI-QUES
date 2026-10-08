"""Spark validation/enrichment of the canonical multi-source dataset; run explicitly."""
import argparse,json,os,sys
from pathlib import Path
from pyspark.sql import SparkSession,functions as F,Window
from data_engineering.pipeline import export_frame
def run(directory):
    os.environ.setdefault('PYSPARK_PYTHON',sys.executable)
    os.environ.setdefault('SPARK_LOCAL_IP','127.0.0.1')
    path=Path(directory).resolve()
    spark=SparkSession.builder.master('local[2]').appName('FDACanonicalValidation').config('spark.sql.shuffle.partitions','4').getOrCreate()
    spark.sparkContext.setLogLevel('ERROR')
    try:
        df=spark.read.parquet(str(path/'canonical_inspections.parquet'))
        df=df.withColumn('inspection_date',F.to_date('inspection_date'))
        df=df.withColumn('inspection_year',F.year('inspection_date'))
        df=df.withColumn('source_project_rows',F.get_json_object('payload_json','$.source_project_rows').cast('long'))
        df=df.withColumn('available_citations',F.get_json_object('payload_json','$.available_citation_count').cast('long'))
        stats=df.agg(F.count('*').alias('inspections'),F.countDistinct('inspection_id').alias('distinct_ids'),
                     F.sum('source_project_rows').alias('project_rows'),F.sum('available_citations').alias('citation_rows')).first().asDict()
        q=json.loads((path/'quality.json').read_text(encoding='utf-8'))
        assert stats['inspections']==stats['distinct_ids']==q['valid_records']
        assert stats['project_rows']==q['total_records']
        expected=next(s['rows'] for s in q['source_files'] if s['kind']=='citations')
        assert stats['citation_rows']==expected
        summary=df.groupBy('fei_number').agg(F.count('*').alias('inspection_count'))
        enriched=df.join(summary,'fei_number','left').withColumn('recency_rank',F.row_number().over(Window.partitionBy('fei_number').orderBy(F.col('inspection_date').desc(),'inspection_id')))
        annual=enriched.filter(F.col('inspection_date').isNotNull()).groupBy('inspection_year','classification').agg(F.count('*').alias('inspection_count'))
        export_frame(annual,path/'spark_annual_validation.parquet')
        (path/'spark_validation.json').write_text(json.dumps({'engine':'PySpark','status':'passed',**stats},indent=2),encoding='utf-8')
        print(stats)
    finally:spark.stop()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',default='data/real');a=p.parse_args();run(a.directory)
