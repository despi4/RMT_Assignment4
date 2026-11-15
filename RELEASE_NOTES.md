# Final research manuscript reproducibility package

Continuation of Assignment 4: a controlled study of factual access and
abstention in Qwen2.5-0.5B-Instruct under distracting synthetic context.

- Preserves all 28 frozen source files and 2,520 original model responses.
- Reproduces the paper's numerical Results with Python standard library only.
- Adds a clearly post-hoc template extractor, not a new model run.
- Provides the exact manuscript figure renderer and all 13 course checklist items.
- Includes diagnostic tests, human-review forms and official journal checks.
- GitHub Actions recalculates archived results; it does not repeat inference.

Run from the repository root:

```sh
python final_tools/analyze_public.py
python -m unittest discover -s final_tools -p "test_public.py" -v
```

The named manuscript, journal-fit/checklist appendices, cover letter, slides,
Russian defence guide and LaTeX source are supplied as a separate course
package. Personal confirmations and university reports are not public code.

The tag `final` identifies the course release. It does not certify that human
review, author declarations, outside-team inference replication or university
similarity review are complete. See `final_tools/final_readiness.csv` for
documented status. Publication in a journal is voluntary and not guaranteed.
