"""Spark canonicalization with quarantine, reproducible IDs and bounded driver export."""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

CANONICAL = ['inspection_id','fei_number','company_name','site_name','inspection_date',
             'country','product_type','inspection_type','classification','citation_flag',
             'observation_count','project_area','observation_text','fiscal_year']

def read_source(path):
    path=Path(path)
    if not path.exists(): raise ValueError(f'Dataset not found: {path}')
    try:
        if path.suffix.lower()=='.csv': return pd.read_csv(path,dtype=str,keep_default_na=False)
        if path.suffix.lower() in ('.xlsx','.xls'): return pd.read_excel(path,dtype=str).fillna('')
        if path.suffix.lower()=='.parquet': return pd.read_parquet(path).fillna('').astype(str)
    except Exception as exc: raise ValueError(f'Cannot read dataset: {exc}') from exc
    raise ValueError('Supported formats: CSV, XLSX, XLS (with xlrd), Parquet')

def transform(spark, source, mapping, as_of):
    from pyspark.sql import functions as F, Window
    if len(set(mapping.values())) != len(mapping.values()): raise ValueError('Map each source column to only one canonical field')
    unknown=set(mapping)-set(CANONICAL)
    if unknown: raise ValueError(f'Unknown canonical fields: {sorted(unknown)}')
    if not any(mapping.get(k,k) in source.columns for k in ['company_name','fei_number','site_name']):
        raise ValueError('Map at least one identity: company_name, fei_number or site_name')
    values=[]
    for i,record in enumerate(source.to_dict('records'),2):
        values.append(tuple([str(record.get(mapping.get(k,k),'') or '') for k in CANONICAL]+[str(i),json.dumps(record,default=str)]))
    df=spark.createDataFrame(values, schema=', '.join(f'{k} string' for k in CANONICAL+['source_row','source_record']))
    for col in CANONICAL:
        df=df.withColumn(col,F.when(F.trim(F.col(col))=='',None).otherwise(F.trim(F.col(col))))
    df=df.withColumn('company_name',F.regexp_replace('company_name',r'\s+',' '))
    df=df.withColumn('company_key',F.lower('company_name'))
    df=df.withColumn('raw_classification',F.col('classification'))
    normalized=F.upper(F.regexp_replace('classification',r'[^a-zA-Z]',''))
    df=df.withColumn('classification',F.when(normalized.isin('NAI','NOACTIONINDICATED'),'NAI')
        .when(normalized.isin('VAI','VOLUNTARYACTIONINDICATED'),'VAI')
        .when(normalized.isin('OAI','OFFICIALACTIONINDICATED'),'OAI'))
    df=df.withColumn('raw_date',F.col('inspection_date'))
    df=df.withColumn('inspection_date',F.coalesce(*[F.to_date(F.try_to_timestamp('raw_date',F.lit(fmt))) for fmt in ['yyyy-MM-dd','MM/dd/yyyy','yyyy-MM-dd HH:mm:ss']]))
    df=df.withColumn('raw_count',F.col('observation_count'))
    df=df.withColumn('observation_count',F.expr('try_cast(try_cast(observation_count as double) as int)'))
    df=df.withColumn('citation_indicator',F.when(F.lower('citation_flag').isin('true','yes','1','y'),1)
        .when(F.lower('citation_flag').isin('false','no','0','n'),0))
    df=df.withColumn('rejection_reason',F.concat_ws('; ',
        F.when(F.col('raw_date').isNotNull() & F.col('inspection_date').isNull(),'Invalid date'),
        F.when(F.col('inspection_date')>F.lit(as_of),'Future inspection date'),
        F.when(F.col('raw_count').isNotNull() & (F.col('observation_count').isNull() | (F.col('observation_count')<0) | (F.expr('try_cast(raw_count as double)')!=F.col('observation_count'))),'Invalid observation count'),
        F.when(F.coalesce('company_name','fei_number','site_name').isNull(),'Missing identity')))
    # Stable source-derived IDs only when source has no ID; never synthetic inspection facts.
    df=df.withColumn('inspection_id',F.coalesce('inspection_id',F.concat(F.lit('DERIVED-'),F.sha2(F.concat_ws('|',*[F.coalesce(F.col(k),F.lit('<null>')) for k in CANONICAL if k!='inspection_id']),256))))
    w=Window.partitionBy('inspection_id').orderBy(F.col('source_row').cast('int'))
    df=df.withColumn('duplicate_rank',F.row_number().over(w)).cache()
    duplicates=df.filter(F.col('duplicate_rank')>1)
    rejected=df.filter((F.col('duplicate_rank')==1)&(F.col('rejection_reason')!=''))
    valid=df.filter((F.col('duplicate_rank')==1)&(F.col('rejection_reason')==''))
    valid=valid.withColumn('inspection_year',F.year('inspection_date')).withColumn('inspection_month',F.month('inspection_date'))
    valid=valid.withColumn('inspection_recency',F.datediff(F.lit(as_of),'inspection_date'))
    for classification in ['OAI','VAI']:
        valid=valid.withColumn(f'{classification}_indicator',F.when(F.col('classification').isNotNull(),(F.col('classification')==classification).cast('int')))
    valid=valid.withColumn('site_key',F.coalesce('fei_number',F.concat_ws(' | ',F.coalesce('company_key',F.lit('unknown')),F.coalesce('site_name',F.lit('unspecified')))))
    valid=valid.withColumn('country',F.initcap('country')).withColumn('product_type',F.initcap('product_type'))
    summary=valid.groupBy('site_key').agg(F.count('*').alias('site_inspection_count'))
    valid=valid.join(summary,'site_key','left')
    valid=valid.withColumn('inspection_rank',F.row_number().over(Window.partitionBy('site_key').orderBy(F.col('inspection_date').desc_nulls_last(),'inspection_id')))
    counts=df.agg(*[F.sum(F.col(k).isNull().cast('int')).alias(k) for k in CANONICAL]).first().asDict()
    total=df.count()
    quality={'total_records':total,'valid_records':valid.count(),'rejected_records':rejected.count(),
        'duplicate_records':duplicates.count(),'missing_values':counts,
        'invalid_dates':df.filter(F.col('raw_date').isNotNull() & F.col('inspection_date').isNull()).count(),
        'unknown_classifications':df.filter(F.col('raw_classification').isNotNull() & F.col('classification').isNull()).count(),
        'data_completeness_pct':round(100*(1-sum(counts.values())/(total*len(CANONICAL))),2) if total else None,
        'as_of':as_of,'engine':'PySpark','missing_columns':[k for k in CANONICAL if mapping.get(k,k) not in source.columns],
        'notes':['Unknown classifications retained as null; no inferred citation flag.', 'One row per inspection required. Repeated source IDs quarantined for review.', 'Completeness includes optional fields after normalization.']}
    return valid,rejected,duplicates,quality

def export_frame(df,path):
    # Spark local Hadoop writers need winutils on Windows. Arrow writes Spark-produced rows
    # in bounded chunks here; Linux uses native distributed parquet writes.
    if os.name!='nt':
        df.write.mode('overwrite').parquet(str(path)); return
    from pyspark.sql.types import IntegerType,LongType,DateType
    fields=[pa.field(f.name,pa.date32() if isinstance(f.dataType,DateType) else pa.int64() if isinstance(f.dataType,(IntegerType,LongType)) else pa.string()) for f in df.schema.fields]
    schema=pa.schema(fields)
    with pq.ParquetWriter(path,schema) as writer:
        batch=[]
        for row in df.toLocalIterator():
            batch.append(row.asDict())
            if len(batch)>=5000: writer.write_table(pa.Table.from_pylist(batch,schema=schema)); batch=[]
        if batch: writer.write_table(pa.Table.from_pylist(batch,schema=schema))

def run(input_path,mapping_path,output_path,as_of,synthetic=False):
    from pyspark.sql import SparkSession
    os.environ.setdefault('PYSPARK_PYTHON',sys.executable)
    os.environ.setdefault('SPARK_LOCAL_IP','127.0.0.1')
    source=read_source(input_path)
    if source.empty: raise ValueError('Dataset has no records')
    mapping=yaml.safe_load(Path(mapping_path).read_text(encoding='utf-8')) or {}
    spark=SparkSession.builder.master('local[2]').appName('InspectionETL').config('spark.sql.shuffle.partitions','2').config('spark.ui.enabled','false').getOrCreate()
    spark.sparkContext.setLogLevel('ERROR')
    try:
        valid,rejected,duplicates,quality=transform(spark,source,mapping,as_of)
        output=Path(output_path); output.mkdir(parents=True,exist_ok=True)
        for df,name in [(valid,'inspections'),(rejected,'rejected'),(duplicates,'duplicates')]: export_frame(df,output/f'{name}.parquet')
        quality['data_label']='SYNTHETIC DEMONSTRATION DATA' if synthetic else 'USER-SUPPLIED DATA (provenance not independently verified)'
        quality['source_file']=Path(input_path).name
        (output/'quality.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
        return quality
    finally: spark.stop()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--input',required=True); p.add_argument('--mapping',default='config/schema_mapping.yaml'); p.add_argument('--output',default='data/processed'); p.add_argument('--as-of',default=date.today().isoformat()); p.add_argument('--synthetic',action='store_true')
    a=p.parse_args(); print(json.dumps(run(a.input,a.mapping,a.output,a.as_of,a.synthetic),indent=2))
