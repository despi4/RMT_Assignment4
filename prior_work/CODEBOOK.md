# Pilot data codebook

One row = one method result in one source configuration.

| Field | Definition |
|---|---|
| record_id | Unique immutable row identifier. |
| study_id | Citation key; joins screening/source manifest. |
| source_url | Official article URL; syntax validated, reachability not checked by pipeline. |
| source_location | PDF/printed page, table, task, model and column; manually verify. |
| model | Exact table model label; Yang labels vary across sections. |
| model_version | Reported checkpoint, otherwise NR and explicit uncertainty. Matching NR is not verification. |
| dataset | Source task label including 0-shot where applicable. |
| split | Source-reported evaluation; precise split metadata may remain unavailable. |
| fact_category | newly_introduced, existing_seen, common_popular, rare_long_tail or not_specified. |
| source_fact_category | Original source terminology; never automatically equate seen and popular. |
| category_definition | Exposure or popularity rationale and its limitations. |
| method | BASE, RAG, UFT or SFT; BASE may already be instruction-tuned. |
| variant | base, rag, uft, uft_par or sft; each is an intervention arm. |
| metric | Only accuracy supported in this pilot; exact match requires a documented extension. |
| value | Original numerical source value; no imputation. |
| unit | fraction in [0,1] or percent in [0,100]. |
| higher_is_better | TRUE or FALSE, explicitly declared. |
| group_id | Candidate configuration group; matching fields still checked. |
| evaluation_task | English multiple-choice QA, a bounded proxy for factual answering. |
| scoring | Option/label likelihood or classification head. SFT mismatch triggers qualified interpretation. |
| baseline_id | Record identifier for the source-provided BASE arm. |
| training_data | What the intervention trains on; corpus and labelled-QA access differ. |
| retrieval_data | External corpus used at inference, otherwise not applicable. |
| conditions | Manual fairness context; not automatically certified. |
| verification_status | Source audit during revision; independent student verification still pending. |

## Missingness and inclusion

NR is permitted for unreported textual metadata. Required cells cannot be empty.
Numerical NR, NaN, infinity or out-of-range accuracy is rejected, never converted
to zero. Exact model versions and detailed splits are not independently established;
shared source labels make descriptive contrasts possible without resolving that uncertainty.

## Comparisons

The program requires all MATCH fields in pipeline.py to agree. UFT scoring must
match RAG scoring. SFT's different classification head is retained only as an
explicitly qualified source-reported contrast. The program does not automatically
certify equivalent corpora, compute budgets, prompts or information access.

RAG minus FT pp = RAG in percentage units minus FT in percentage units.
A negative accuracy difference favors FT. BASE contrasts use the same transformation.
FT-par effects can be inspected against FT-reg in the source data. Configuration
counts and contrasts share arms; they are not independent statistical samples.

## Pilot selection

Ovadia Table 2: all three models, BASE/RAG/FT-reg/FT-par (12 rows).
Ovadia Table 1: Anatomy 0-shot, first two models, BASE/RAG/FT (6 rows).
Yang Table 2: all three models, BASE/RAG/UFT/SFT (12 rows).
This is a deliberately small auditable subset, not an exhaustive result extraction.
The original two-model Anatomy selection is retained for continuity with the supplied
pilot, not as a claim that the third model is ineligible. Extend extraction before
making exhaustive statements about either paper.
