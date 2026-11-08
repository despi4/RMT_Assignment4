# RMT Assignment 4

**Код и данные эксперимента о влиянии отвлекающего контекста на точность LLM. Отчёт не включён.**

[Открыть в Google Colab](https://colab.research.google.com/github/despi4/RMT_Assignment4/blob/main/Run_in_Colab.ipynb) · [Порядок действий](START_HERE_RU.txt) · [Протокол](docs/PROTOCOL.md)

Проверено: 19 программных тестов и 63 настоящих dev-ответа Qwen. Финальный эксперимент: 120 фактов × 7 условий × 3 конфигурации контекста = 2520 ответов; он выполняется после загрузки протокола в Moodle.

## Technical instructions

This package adds a controlled factual-QA experiment to Assignment 3's literature synthesis. It studies context use, supporting Objective 4, without rerunning fine-tuning. No final LLM results are supplied or fabricated. Nineteen software tests passed. A real 63-call CPU development smoke test is preserved in validation/dev_smoke_63; this is not final test evidence.

[Open the notebook in Google Colab](https://colab.research.google.com/github/despi4/RMT_Assignment4/blob/main/Run_in_Colab.ipynb). Start with `START_HERE_RU.txt`. The first notebook cell clones this repository automatically. Select a GPU runtime. Run the notebook in order. Keep a backup of the project after long runs because Colab sessions can disconnect. A small model is used for feasibility; null or mixed results are valid.

## Package contents

- config/experiment.json: fixed design, prompts, model and analysis settings.
- data/: 30 dev facts, 120 final facts, 630 dev stimuli and 2520 final stimuli; fictional stimuli, NOT model predictions.
- scripts/: generation, preparation, freezing, inference, paired analysis and manual error review.
- tests/: invariants, scoring and statistical checks; artificial test fixtures are not research observations.
- docs/PROTOCOL.md: prospective freeze content; transfer it into the required Appendix A submission form.
- docs/CONTINUITY.md, CRITERIA_AUDIT.csv and DEFENCE_RU.txt: continuity, requirement audit and defence preparation.
- results/software_test_log.txt: software checks only. Real model outputs will appear in results/final/.

## Installation

Use Python 3.11 or 3.12 and a virtual environment, or Colab. For a GPU, use an environment whose installed PyTorch supports that GPU. Internet is needed for dependencies and the public model download. No paid API or API key is required for this public checkpoint.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/prepare.py
python scripts/run.py --phase pilot --limit-facts 3
```

Pilot uses development data only. For a full development check, set `--limit-facts 30` (630 calls). Adjust settings using dev only, document decisions, rerun tests/prepare, then upload the completed protocol. Do not change code or install different packages after freezing.

## Freeze before final inference

The course requires a Moodle timestamp before final runs. Complete Appendix A, add the real checkpoint SHA, hardware, package versions and dataset manifest hashes; upload it and save the actual receipt. Then run, substituting your true details:

```bash
python scripts/freeze.py --uploaded-at "ACTUAL_ISO_TIMESTAMP_WITH_TIMEZONE" --evidence "path/to/actual_moodle_receipt.png" --declarant "YOUR NAME"
```

The timestamp is declared by the student; instructor verification still uses Moodle. This command never manufactures a receipt. It seals the code, configuration, dataset and actual environment. There is no override in the final runner.

## Execute and analyze

```bash
python scripts/run.py --phase final
python scripts/analyze.py
```

Final inference makes 2520 calls. It appends raw responses and can resume an interruption when existing rows are complete. Failed calls remain in the log and stop execution; see the protocol for an explicitly versioned rerun. Do not erase failures.

Analysis exports main_results.csv, per_seed.csv, paired_comparisons.csv, subgroups.csv, answerability_confusion.csv, audit_rows.csv, four standalone SVG figures and error_review.csv. A completed raw log is mandatory; analysis rejects pilot and fixture backends. Exact model call compatibility and GPU feasibility still need the real development run in your runtime.

The PRIMARY metric is actual gold-city recall for ALL conditions, including closed_book. expected_response_accuracy_pct is a SECONDARY instruction/abstention metric: a correct UNKNOWN is expected in absent-evidence controls but does not mean the model knew the city.

## Human error review

Two students label all sampled errors independently in error_review.csv, adjudicate final_category and provide a case-specific explanation. Preserve the original separate labels. Then run:

```bash
python scripts/review_errors.py --rater-1-name "ACTUAL FIRST RATER" --rater-2-name "ACTUAL SECOND RATER"
```

Generated categories/counts are not invented by the program. Full error review and interpretation remain human work.

## Finish the report and reproduce

Prepare your separate Word report using the real generated tables and readable SVG figures. The report is intentionally outside this code repository. Write 1800-2500 words of Results/Discussion as specified in the assignment, not a padded description of Python. Mark H1-H3 honestly, compare at least three studies from Assignment 1 (verify they were actually in Assignment 1; that document was not provided), and explain specific limitations. The four papers in docs/REFERENCES.txt are verified primary sources; three also occur in supplied Assignment 3.

Keep Assignment 3's reviewed FT/RAG evidence separately. Its original code/data archive was located and included in prior_work. The 30 input rows and 14 contrasts were recomputed, 12 original tests passed, and numeric cell matches are recorded in prior_work/recomputed/source_cell_check.csv. This package cannot manufacture the missing common/rare category coverage.

For independent reproduction, copy the frozen release to a new folder or clean runtime, preserve/copy the original final logs elsewhere, then run the same commands. The strict environment check is intentional. If hardware or dependency versions differ, document this as a reproduction deviation and compare discrepancies. Complete Appendix C with the actual second person's actions; do not prefill a successful outcome.

Create your own GitHub/GitLab repository, include code, data, actual logs, readable figures, environment lock and completed appendices, then:

```bash
git add .
git commit -m "Complete Assignment 4 reproducible experiment"
git tag assignment-4
git push origin HEAD
git push origin assignment-4
```

Publish only after checking for API keys, passwords and personal receipt data. This repository contains code and supporting evidence; it is not a completed Moodle submission. The assignment-4 release tag should be created after actual final results and independent reproduction are included. The assignment says max two students; the old report lists three. Resolve team membership with the instructor. Its scoring text also conflicts (10+10 out of 20 versus a final 20/80 line); confirm the applicable weights.

## Limits of the study

This is controlled supplied context, an oracle/controlled-retrieval approximation. It does not implement or benchmark a search engine, prove training exposure, update model weights or demonstrate permanent acquisition of knowledge. Data are synthetic, one model and one language. Longer contexts differ from clean contexts in both length and irrelevant content. Source matching in distractor-type contrasts is approximate. The positions are counterbalanced, but associated context samples change. Tests are paired over fact clusters; 2520 calls are not 2520 independent facts.

Software is MIT licensed; the synthetic dataset is CC0 (see DATA_LICENSE). Original assignments and published articles retain their original rights. Qwen model weights are downloaded under the model's own license, not redistributed here. Declare AI assistance in code, stimuli and writing according to course policy; students verify all content and results.

## Independent reproduction without overwriting results

In a clean environment, install the locked dependencies and obtain the same source/data/freeze. The reproduction mode keeps the original final results intact and explicitly records environment differences. It is not permission to retune the model.

```bash
python scripts/run.py --phase reproduction --run-id independent_1
python scripts/analyze.py --reproduction-id independent_1
python scripts/compare_reproduction.py --run-id independent_1 --person "ACTUAL REPRODUCER" --commit "ACTUAL COMMIT" --notes "Actual differences and README fixes"
python scripts/submission_check.py
```

For oral defence, trace an accuracy with `python scripts/trace_number.py --condition similar_16` and optionally `--record-id ACTUAL_ID`.

## Previous study reproduction

`prior_work` is the original Assignment 3 project, with its original files preserved. `prior_work/recomputed` contains the actual rerun (30 input rows, 14 contrasts, 12 passing tests) and a 30-cell numerical cross-check against the source tables. These are published-study observations, NOT new Qwen observations. Never merge their accuracy values into the synthetic experiment.
