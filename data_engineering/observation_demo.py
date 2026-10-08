"""Observation-level synthetic fixtures; original wording, format-inspired only."""
FORMAT_URL='https://www.fda.gov/about-fda/montana-compounding-pharmacy-pc-missoula-mt-483-issued-09202016'
FAQ_URL='https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-references/fda-form-483-frequently-asked-questions'
EXAMPLES=[
('Audit trail controls failed; original records were deleted.','Records and data integrity','Critical',['Data Integrity']),
('The laboratory failed to investigate repeated OOS results.','Laboratory controls','High',['OOS Investigation','Laboratory Controls']),
('CAPA effectiveness was not verified.','Quality management','Medium',['CAPA']),
('Documentation was incomplete for the batch records.','Records and data integrity','Medium',['Documentation']),
('Equipment calibration verification was incomplete.','Laboratory controls','Medium',['Laboratory Controls','Equipment']),
('Process validation did not establish reproducible manufacturing controls.','Production and validation','Medium',['Manufacturing Controls','Validation']),
('Training records were incomplete.','Personnel and training','Medium',['Training']),
('An isolated administrative documentation error had no product impact.','Records and data integrity','Low',['Documentation']),
('No evidence of audit trail failures was observed.','Unclassified','Insufficient evidence',[]),
('The computer access control was disabled.','Records and data integrity','High',['Computer Systems']),
('The quality unit failed to review repeated deviation reports.','Quality management','High',['Quality Systems','Deviation Management']),
('Equipment maintenance was incomplete.','Facilities and equipment','Medium',['Equipment']),
]
def records():
    result=[]
    for site in range(2):
        for year in range(2023,2026):
            for i,(text,category,severity,themes) in enumerate(EXAMPLES):
                result.append({'observation_id':f'DEMO-{site}-{year}-{i+1:02}','inspection_id':f'DEMO-INS-{site}-{year}','company_name':['Aster Demonstration','Cedar Demonstration'][site],'site_name':f'Fictional site {site+1}','inspection_date':f'{year}-04-15','observation_number':i+1,'observation_text':text,'synthetic':True,'template_id':f'FORMAT-483-{i+1:02}','format_source_url':FORMAT_URL,'source_locator':'Form header fields and numbered observations, pages 1-3; wording and labels independently authored','expected_category':category,'expected_severity':severity,'expected_themes':themes,'label_authority':'developer fixture; not expert ground truth'})
    return result
