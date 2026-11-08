# Assignment 3 research implementation

Authors: Madiuly Almadi, Aibek Galymbekov, Aidyn Zhubanyshev. Group SE-2417.

This is a secondary analysis of published results, not a new model experiment.
Python 3.10 or newer is recommended. There are no third-party runtime dependencies.

## Run

From this directory:

```bash
python pipeline.py --input data/results.csv --output outputs
python -m unittest discover -s tests -v
```

Expected: 30 method results, 2 numeric studies, 8 configurations, 14 FT/RAG contrasts,
3 qualified SFT contrasts, 0 structurally rejected pairs. Twelve tests should pass.
The source pilot has no direct popular/rare FT/RAG pairs.

## Evidence

- data/results.csv: original fractional source values and provenance.
- data/screening_log.csv: all four identified papers and decisions.
- data/search_log.csv: targeted audit only; not a systematic search.
- data/source_manifest.csv: official source URLs, access date and original PDF hashes.
- data/contextual_evidence.csv: contextual mechanism/category observations.
- data/reviewer_checklist.csv: independent student checks remain pending.
- outputs/comparisons.csv: UFT and SFT contrasts, baseline contrasts and qualifications.
- outputs/rejected_pairs.csv: header only for this structurally compatible pilot.
- outputs/summary.json: coverage and input SHA-256.
- outputs/runtime.json: exact execution environment.
- outputs/test_output.txt: actual captured test transcript.

Download papers from the official URLs to verify cells. Do not treat matching unknown
fields as evidence that unknown model checkpoints or splits were identical. SFT uses
a classification head and labelled QA; those comparisons are qualified, not isolated
knowledge-injection effects. Original values remain unchanged. Source PDFs are not
redistributed. Tests mutate copies of input rows; those copies are test fixtures,
not fabricated research observations. No original model training, inference, human
survey, or independent student review is claimed.

## Before submission

Check the revised report and every source cell. Complete the reviewer checklist.
Both the equivalent analytical practical track and the three-person team require
instructor confirmation under the supplied assignment rules. The latter limit a
team to two students; listing three names does not establish approval.
Assignment 2 continuity is documented in ALIGNMENT_BASIS.txt. Follow course AI-use
rules; the extraction, code and report revision were prepared with AI assistance
and require student verification. Do not claim to have personally done steps you
cannot demonstrate or explain.
