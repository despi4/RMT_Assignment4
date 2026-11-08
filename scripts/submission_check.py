"""Honest requirement audit. Prepared software never counts as completed LLM evidence."""
import csv
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT, read_json, utc_now, write_json, write_csv

def audit():
    final=ROOT/'results/final'; analysis=ROOT/'results/analysis'
    def exists(p):return (ROOT/p).is_file()
    complete=False
    if (final/'completion.json').exists():complete=read_json(final/'completion.json').get('run_status')=='complete'
    reviewed=False
    if (analysis/'error_review_status.json').exists():
        reviewed=read_json(analysis/'error_review_status.json').get('reviewed',-1)>=0
    reproduced=any((ROOT/'results/reproduction').glob('*/Appendix_C_Record.json')) if (ROOT/'results/reproduction').exists() else False
    criteria=[
      ('Rule 1','Team max two','Student names and instructor decision','HUMAN CONFIRMATION'),
      ('Rule 2','Original RQ aim objectives and approved design addition','docs/CONTINUITY.md and actual approval reference','PREPARED; VERIFY APPROVAL SCOPE'),
      ('Part 1','Protocol fixed before final inference','freeze/freeze.json and actual Moodle timestamp','RECORDED; INSTRUCTOR VERIFIES' if exists('freeze/freeze.json') else 'PENDING UPLOAD'),
      ('Part 2','Data source version splits distribution hashes','data/manifest.json data/facts.json','IMPLEMENTED'),
      ('Part 2','Two fair baselines','closed_book and clean oracle context; same checkpoint','IMPLEMENTED; ORACLE SCOPE EXPLICIT'),
      ('Part 2','Hardware versions prompts seeds runtime','config/model_lock.json and real metadata','RECORDED' if exists('config/model_lock.json') else 'PENDING MODEL PREPARATION'),
      ('Part 3','Full final evaluation without selected runs','2520 raw calls and validation','LOGGED; VALIDATE USING ANALYZE' if complete else 'PENDING REAL FINAL RUN'),
      ('Part 3','Mean SD and 95 percent uncertainty','main_results.csv','COMPUTED' if (analysis/'main_results.csv').exists() else 'CODE READY; NO FINAL RESULTS'),
      ('Part 3','Statistical test statistic p Holm effect','paired_comparisons.csv','COMPUTED' if (analysis/'paired_comparisons.csv').exists() else 'CODE READY; NO FINAL RESULTS'),
      ('Part 3','Two informative figures','accuracy and sensitivity; extra position and confusion figures','GENERATED' if (analysis/'figure_2_noise.svg').exists() else 'CODE READY'),
      ('Part 4','At least 30 actual errors or all if fewer','error_review.csv with immutable case selection','HUMAN CODING RECORDED' if reviewed else 'PENDING REAL ERRORS AND HUMAN CODING'),
      ('Part 4','Additional sensitivity or subgroup analysis','subgroups.csv sensitivity curve','COMPUTED' if (analysis/'subgroups.csv').exists() else 'CODE READY'),
      ('Part 5','Every hypothesis and objective evaluated','hypothesis_decisions.csv plus original objective coverage matrix','HYPOTHESES COMPUTED; COMPLETE RQ TEXT' if (analysis/'hypothesis_decisions.csv').exists() else 'PENDING RESULTS'),
      ('Part 6','Compare at least 3 actual Assignment 1 studies','docs/A1_SOURCE_CHECK.csv and manually written Discussion','PENDING ASSIGNMENT 1 CONFIRMATION'),
      ('Part 6','Unexpected results practical implications validity limits future work','Actual Discussion in final report','SCAFFOLD ONLY'),
      ('Part 7','README data access environment scripts license','README.md requirements.txt LICENSE DATA_LICENSE','PREPARED'),
      ('Part 7','Independent clean-environment reproduction','Appendix_C_Record.json and separate real logs','COMPARISON RECORDED; CHECK HUMAN ACCOUNT' if reproduced else 'PENDING INDEPENDENT EXECUTION'),
      ('Part 7','Hosted repository and assignment-4 tag','Real GitHub/GitLab URL and published release','STUDENT PUBLICATION REQUIRED'),
      ('NLP track','Full test set subgroups successes failures runtime statistics','Main outputs success_examples.csv manual errors','CODE READY; NEED REAL RESULTS'),
      ('Report','1800 to 2500 words Results and Discussion','Final completed Word report; references and appendices excluded','TEMPLATE ONLY'),
      ('Appendices','A protocol B error table C reproduction','Completed real forms','FORMS PREPARED; EVIDENCE PENDING'),
      ('Integrity','All numbers traceable and no fabricated results','Raw IDs hashes audit_rows.csv and source references','GUARDS IMPLEMENTED; VERIFY ACTUAL SUBMISSION'),
      ('Defence Q1','Explain protocol and fair setup','docs/DEFENCE_RU.txt and actual freeze','STUDENT DEFENCE REQUIRED'),
      ('Defence Q2','Explain main result and statistical test','Actual result and paired test','STUDENT DEFENCE REQUIRED'),
      ('Defence Q3','Explain an error and additional analysis','Actual coded case and sensitivity result','STUDENT DEFENCE REQUIRED'),
      ('Defence Q4','Prior-study comparison and validity threat','Actual Discussion','STUDENT DEFENCE REQUIRED'),
      ('Defence Q5','Trace any selected number to original evidence','scripts/trace_number.py and raw logs','TOOL PREPARED; STUDENT DEMONSTRATION REQUIRED'),
      ('Grading','Resolve contradictory 50/50 and footer 20/80','Instructor clarification','HUMAN CONFIRMATION')]
    rows=[dict(zip(['section','requirement','evidence','status'],r)) for r in criteria]
    write_csv(ROOT/'docs/CRITERIA_AUDIT.csv',rows)
    write_json(ROOT/'docs/CRITERIA_AUDIT.json',{'generated_at':utc_now(),'criteria':rows,
        'interpretation':'Statuses indicate available evidence, not awarded marks. Code readiness is not completed research.'})
    for row in rows:print(f"{row['section']}: {row['status']} | {row['requirement']}")

if __name__=='__main__':audit()
