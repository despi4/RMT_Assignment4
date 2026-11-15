FINAL PAPER ANALYSIS

Requires Python 3.10 or later, standard library only.
From the repository root:

  python final_tools/analyze_public.py
  python -m unittest discover -s final_tools -p "test_public.py" -v

This reproduces every numerical table and figure in the final manuscript
Results section from the original archived responses. It verifies all 28
frozen source hashes, the raw response SHA256, completeness and scoring.
It does not download models and does not require a private Moodle receipt.

Outputs are in results/final_paper:
table_1_results.csv: counts, accuracy, SD, intervals, expected accuracy and latency.
table_2_contrasts.csv: H1-H3 paired intervals and Holm-adjusted p values.
table_3_diagnostics.csv: all automatic failure categories.
table_4_positions.csv: descriptive position subgroup counts.
per_seed.csv: context-seed outcomes.
extractor_outputs.csv: every post-hoc deterministic control output.
summary.json: integrity checks and machine-readable paper numbers.
figure_1_accuracy.svg, figure_2_position.svg, figure_3_abstention.svg,
figure_4_extractor.svg: standalone vector plots.

Manuscript table 1 is a literature comparison, not an experimental result.
Manuscript tables 2-4 correspond to result tables 1-3 above.
Manuscript figures 1-3 correspond to figures 1-3 above; the extractor is
reported numerically in the paper, with figure_4 supplied as an optional plot.

New analysis and extraction control dated 16 November 2026. Original
outcomes were known before construction. No new LLM inference was performed.
No fine-tuning or learned retrieval method is claimed. The extractor accepts
only visible question and context; it never receives the gold answer.
Its known synthetic sentence grammar makes it a diagnostic control only.

For genuine independent model inference, follow the ORIGINAL README section
on reproduction with a separate run-id and the archived checkpoint/runtime.
Retain the actual runner, date, hardware, package versions, commands and logs.
An author's reported rerun is not independently verified without its files.

Original tests: 26 completed successfully in the document-building environment;
one requires torch, which was absent there. No all-tests-pass claim is made for
that environment. The final_tools tests use no torch and are checked separately.
Original environment.lock.txt is retained without modification.

The public remote has not been updated by this packaging step. The accompanying
Git bundle contains a local tagged release named final. Restore with:
  git clone final.bundle RMT_Final
  cd RMT_Final
  git checkout final

The release name is the course-required packaging label, not a certification
that journal indexing checks, author signatures or human reviews are complete.
