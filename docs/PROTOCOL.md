# Experiment Protocol Freeze

Status: prospective protocol version 2 after criterion audit; no final test outcomes have been obtained. No final LLM outcomes have been obtained by this package's author. This form must be completed and uploaded to Moodle BEFORE final inference. The team reported that adding the experiment is permitted; attach the actual instructor approval reference and identify the permitted scope. A code check is not verification of a Moodle upload.

## Continuity with Assignment 3

Umbrella topic: How does an LLM acquire knowledge?

Retained Assignment 3 title: Comparing Fine-Tuning and Retrieval Augmentation for Factual Accuracy in Large Language Models.

Retained primary research question: What differences do published empirical studies report between fine-tuning and retrieval augmentation in factual accuracy for common, rare, and newly introduced facts in pretrained LLMs on English factual question-answering tasks?

Retained aim: To compare published evidence on how fine-tuning and retrieval augmentation affect factual accuracy for common, rare, and newly introduced facts in pretrained LLMs answering English factual questions.

Retained objectives:
1. Distinguish pre-training, factual fine-tuning, instruction tuning, and retrieval-based access, using pretrained knowledge as the baseline.
2. Classify empirical findings by common, rare, and newly introduced facts, retaining the source definitions and evidence of exposure.
3. Compare accuracy outcomes for fine-tuning and retrieval against available baselines, prioritising comparisons within the same study.
4. Examine how training-data repetition, retrieval relevance, and context use relate to factual gains or failures.
5. Evaluate evidence consistency and limitations to formulate qualified conclusions about when each approach supports reliable factual answers.

Approved addition proposed for Assignment 4: a controlled context-quality experiment supporting Objective 4 and the external-knowledge aspect of Objective 1. The structured review from Assignment 3 remains a separate evidence stream. The original review files are now included in prior_work. Thirty numerical source cells have been checked and fourteen contrasts recomputed. Twelve original software tests passed. Retain their qualified SFT labels and common/rare coverage gaps. No new fine-tuning experiment is claimed. Do not combine accuracy values from this experiment and published FT/RAG tables in one numerical average. Common/rare fact coverage is not provided by the synthetic experiment.

Supplementary empirical question: How do distractor quantity, distractor type, and target-fact position affect a small LLM's use of newly supplied synthetic facts in English question answering?

Suggested report subtitle: A controlled follow-up on contextual factual accuracy and distracting evidence.

## Implementation update before final inference

The team reports that Appendix A was uploaded. Later technical fixes are recorded in docs/IMPLEMENTATION_UPDATE.json. Preserve the original uploaded document and real receipt. Include the update and source commit in Deviations from the frozen protocol; do not overwrite an existing freeze. The selected runtime is CPU float32, two threads, eager attention, schedule seed 952 (config/runtime.json). The model, stimuli, seeds, metrics and statistical design remain as in the uploaded form.

## Decisions to freeze

Students and group: Madiuly Almadi, Aibek Galymbekov, Aidyn Zhubanyshev; SE-2417. The team reports instructor permission for three students.
Instructor approval and scope: the team reports permission for the supplementary experiment and a three-student group. No dated written reference has been supplied.
Model: Qwen/Qwen2.5-0.5B-Instruct, immutable revision from config/model_lock.json. Instruction-tuned checkpoint; "closed_book" means no supplied facts, not an untrained model. All conditions use the SAME checkpoint with no parameter updates.

Data: data version 1.0. 30 development facts and 120 test facts, all fictional countries/cities generated with seed 2417. English prompts; three question forms balanced across facts. No humans or personal data. Every test fact is present in its supported contexts, but no test entity-answer association appears in a development prompt. Questions, contexts, and answers have an auditable source in data/facts.json. Fictional random mappings reduce prior factual knowledge; zero prior exposure cannot be proven for arbitrary name fragments.

Units: 120 fact clusters; one question per fact; three context seeds. Repeated evaluations of the same fact are NOT independent sample units. Context seeds 17, 29, 43 change distractor samples and target position. Decoding is greedy/deterministic; these are not independent training seeds.

Conditions:
- closed_book: no context, simple no-intervention baseline.
- clean: exactly one relevant sentence, strong oracle-context baseline.
- irrelevant_4 and irrelevant_16: target sentence plus 4 or 16 unrelated lake facts.
- similar_4 and similar_16: target sentence plus 4 or 16 other-country capital facts.
- target_absent_16: 16 capital distractors without the target, negative control.

Planned final calls: 120 x 7 x 3 = 2520. Each condition has 360 calls. Pilot: development split only. The default quick pilot uses 3 development facts (63 calls). No test-based prompt tuning, checkpoint selection, threshold choice or exclusion.

Target position: first, middle or last; each fact appears once at each position across the three context seeds for supported noisy conditions. The 4-distractor set is a subset of the 16-distractor set within fact/seed. Distractor data remain within the same split. Approximate character-length matching of capital/lake templates does not guarantee equal token lengths. Record token counts. Clean versus noisy combines length and content effects. Position subgroup findings are descriptive because distractor samples also change across seeds.

Prompt: exact system and user templates in config/experiment.json and scripts/make_data.py. No few-shot examples. The model is instructed to answer with one city or UNKNOWN if evidence is absent. No chain-of-thought requested. Maximum 2048 input tokens and 16 output tokens. No truncation of input is permitted. Output-limit hits are retained and reported.

Primary metric: strict exact-match recall of the actual gold city, reported as accuracy percent, including closed-book factual recall. Normalization: Unicode NFKC, case folding, whitespace normalization, and boundary punctuation stripping only. Accuracy directly measures the fraction of single-gold factual answers recovered; this is the primary question of the study. Extra explanation or multiple answers is incorrect under strict EM; inspect these as format errors. The true city is NOT placed into unsupported prompts.

Secondary measures: expected-response accuracy (city if present; UNKNOWN if absent), unsupported-answer rate for absent evidence, latency median, IQR and p95, input token counts, token-limit hits. In no-evidence controls, correct abstention and factual city recall are different measures; never interpret 100% correct UNKNOWN as factual knowledge.

Primary contrast: similar_16 minus clean, in percentage points. H1: similar_16 has lower factual accuracy than clean. Supported if the effect is negative and two-sided Holm-adjusted p < .05. Otherwise report not supported; report magnitude and uncertainty even when not significant.

H2: clean improves actual city recall over closed_book. Supported if the effect is positive and Holm-adjusted p < .05. Correct UNKNOWN is not the metric for this contrast.

H3: similar_16 has lower factual accuracy than irrelevant_16. Supported if effect negative and Holm-adjusted p < .05. This is a qualified type contrast because token lengths can differ. No assertion of a pure semantic effect.

Statistics: first average each fact's binary result over its three context seeds. Report accuracy mean and sample SD across the three context seeds. Calculate 95% percentile paired/cluster bootstrap intervals by resampling 120 fact clusters (4000 resamples). Differences use paired fact clusters. Use a two-sided sign-flip permutation test on per-fact mean differences (10000 permutations, plus-one p-value); exchangeability under the null is an assumption. Adjust the three prespecified p-values jointly by Holm. Analysis seed 7341. Three context seeds are not enough for a convincing t-test on seed means, so use fact-level paired analysis. Results concern the synthetic sampling scheme and one model; no population-wide claims.

Additional analyses: accuracy by 0/4/16 distractors and distractor type (sensitivity); first/middle/last position and question form (descriptive subgroups); efficiency tables. Do not add unplanned inferential tests without labeling them exploratory. Binary answerability confusion counts and a confusion figure are also exported. Empty output is a failure to answer, not an unsupported substantive answer. Deterministically selected genuine supported success examples are exported alongside failure cases.

Error analysis: review at least 30 failed expected responses, or ALL if fewer. Preselect a condition-stratified sample with unique facts prioritized, seed 991. Two people independently code all selected cases, then resolve disagreements. Categories: distractor_copy, wrong_entity_or_binding, unsupported_answer, unnecessary_abstention, format_error, other. Record actual question, context, expected response, generated answer, two labels and adjudicated explanation. The saved selection manifest prevents accidental removal, substitution or alteration of reviewed cases; identify both human raters in the review command. For zero errors, report zero and do not invent examples. Percentages describe the reviewed sample. Compute agreement and Cohen's kappa where defined.

Fairness: same model revision, prompt policy, preprocessing, question, output budget and device in all conditions. Only context differs. Interleave condition evaluations with a fixed shuffled schedule; discard one warm-up generation. Log hardware, environment and package lock. Speed measurements are descriptive and can vary across reproduction machines.

Failures: log every attempted inference. Preserve failed calls. Complete analysis refuses missing/duplicate/error calls. Correct an execution failure only with a documented deviation and separate versioned run, keeping original logs. Do not change hyperparameters to improve test outcomes.

## Reproducibility and declarations

Run prepare.py after dependencies and development decisions are finalized; it resolves the immutable checkpoint and saves environment.lock.txt. Fill Appendix A with the model revision, manifest hashes and exact hardware. Upload Appendix A plus the lock/config/data manifest to Moodle. Save the real upload receipt and date. freeze.py records the student's declaration and receipt hash. It does not independently authenticate Moodle.

Final raw.jsonl contains each stimulus, response, generated token IDs, metrics, timestamp, checkpoint and prompt hash. Analysis exports per-seed results, paired comparisons, audit rows, figures, error review and provenance. Keep raw files, scripts, completed appendices, environment files and the assignment-4 release. Do not publish personal Moodle receipts; provide a redacted copy if necessary and keep original verification for the instructor.

Reproduction: another student uses a clean environment and the SAME checkpoint, data, config and frozen source versions. Record results and any device/environment changes in Appendix C. Re-running on a different device may alter exact outputs; compare accuracy values and token-level discrepancies honestly. Preserve the initial final run before a new reproduction run. Same hardware/software is the strict reproduction target. Run with --phase reproduction --run-id independent_1 in a separate environment; this never overwrites final logs and records environment differences. Analyze with --reproduction-id independent_1, then compare using compare_reproduction.py with the actual person and commit. Source/config/data hashes must still match the original freeze.

Approval reference: [complete]. Actual Moodle upload timestamp and timezone: [complete]. Receipt file: [complete]. Model revision: [from model_lock.json]. Dataset hashes: [from data/manifest.json]. Hardware and software versions: [complete].

Deviations since upload: [none only if verified; otherwise specify date, reason, before/after settings, whether test outcomes had been seen, instructor approval if scope changed, and affected results].
