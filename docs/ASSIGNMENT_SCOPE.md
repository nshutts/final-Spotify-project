# Assignment scope and requirements checklist

Source: Final Assignment, Multi Agent Large Data Processing Pipeline (30% of grade).
Due: Oct 20, 2026, 11:59 pm PT (extended from Oct 13). Single deliverable: public GitHub repo URL via bCourses.

## The question
Advise Spotify on where the next quarter of product effort should go: access, usability, playback, or billing/support. Answer with an inspectable pipeline and a memo whose every number traces to saved calculations and review IDs.

## Inputs (dataset ZIP from Google Drive, 11 files)
- `spotify_reviews_18months.csv`: 660,622 rows, 97,400,616 bytes, May 2022 to Nov 2023
- Fields: review_id, review_text (multiline), review_rating (1-5, not severity), review_likes, app_version (often missing), review_timestamp (no timezone)
- Known facts to verify: 13 empty texts, 159,701 missing app versions, no repeated IDs, 484,189 distinct nonempty texts
- `cost_100.csv` (first 100 of `checkpoint_500.csv`, nested in `analysis_10000.csv`)
- `golden_50_to_label.csv` (blank human-label columns; separate from all dev files)
- `manifest.json`, `README.md`, `prepare_dataset.py`, `GRADING_CONTRACT.md` (exact schema, hashing, label boundaries), `COST_CALCULATOR.md` (calculator spec), `check_submission.py` (zero-API checker)
- Raw CSV need not be committed; link it and record its checksum.

## Shared labels (fixed)
- Topics (exactly 8): access, usability, playback, downloads, catalog, billing, support, other
- Intents, in precedence order: cancellation > complaint > request > praise > unclear
- Severity 1-5: 1 none/praise/unclear/pure request; 2 annoyance/generic criticism; 3 degraded with some use left; 4 core task blocked; 5 explicit serious financial, privacy or data harm
- Rules: highest-severity specific problem, first mentioned on a tie; for praise, first praised feature; paid-plan mention alone is not billing; bare boycott slogans are unclear; stars, anger or cancellation intent alone do not set severity
- Subtopics optional; add examples

## Record schema (every completed record)
review_id, source_sha256, status, topic, intent, sentiment (-1 to 1), severity (int 1-5), entities, evidence_quote (exact source substring), needs_review, label_config.
Statuses: pending, completed, quarantined (with reason and attempt count). Empty texts quarantined as `empty_review_text`.

## Six stages (distinct roles, code-orchestrated)
1. Prepare (code/SQL): read all rows, preserve IDs and values, profile, find exact duplicates, queue pending. Output: ingestion report, manifest, pending IDs.
2. Classify (model, e.g. Jev or Claude Haiku): all 660,609 nonempty reviews, max 50 per request, validate every returned ID, save after each batch, retry invalid output once then quarantine, exact-text cache with cache_source_id provenance.
3. Verify (separate model task): relabel a declared random sample blind to the first prediction; code compares; disagreement report; planted wrong label in a separate test copy.
4. Group (code, model may name issues from bounded examples): stable issue IDs with all member review IDs for complaint/cancellation records; save accepted mapping.
5. Rank (code only): priority = complaint_count x mean_severity = severity_sum; count each review once per issue; sort score desc, then issue ID asc.
6. Recommend (model): memo from saved aggregates plus bounded evidence pack only; code checks cited IDs and numbers; human reviews argument.
Each stage needs a defined input, output, owner, failure behavior and stop condition. Orchestrator owns dispatch, state, validation, budgets and logs.

## Controls
- Max 50 reviews per enrichment request; bounded retries with backoff and jitter
- Spend cap with reservation before dispatch, output-token cap, max workers, fallback fraction cap (Sonnet 5 fallback only within a declared quota)
- Start with 1 worker; shared rate limits and one spend ledger
- Atomic saves per batch; resume without paying to relabel completed IDs
- Model allowlist; versioned prompts and settings; lowest effort that passes evals

## 100-review cost/runtime calculator (T3, see COST_CALCULATOR.md)
- Real cold run on `cost_100.csv` unchanged, empty cache, 1 worker, covering enrichment, declared verification sample, grouping, ranking and memo
- Warm rerun shows zero new enrichment calls; disclose downstream calls
- Default offline mode recomputes cost from saved usage and editable rates, no API key; paid run is a separate explicit command
- By stage: provider, model/effort, prompt/schema version, batch size, workers, completed/failed, unique texts, cache hits, requests/attempts, usage, price units, currency, dated source links
- Report cost per 1,000 inputs, cost per completed record, throughput, cold/warm wall-clock time; separate API spend, local compute and unknown costs
- Billing = units x unit price; input, cached-input and output mutually exclusive; no double counting reasoning
- Full-run projection: 660,622 rows, 660,609 classifications, 13 quarantines, 484,189 distinct texts; no-reuse comparison; base and conservative scenarios; fixed overhead once; budget-exceeded flag
- Refresh estimates at 500 and 10,000
- Files under `cost/`: pilot_records.jsonl, pilot_calls.jsonl, rates.csv, usage.csv, report.md/html, replay instructions
- Grader check: doubling rates doubles API spend only; changing projected volume does not change measured pilot results

## Evaluation
- Hand-label all 50 golden reviews (Natalie, by hand) before the final eval; never put their labels in prompts, examples, thresholds or issue discovery
- Report topic and intent agreement, severity exact agreement and MAE, ambiguous count, per-topic counts, confusion table
- Sentiment: predeclared tolerance or MAE; evidence_quote: exact-substring check in code plus support check; entities: unsupported additions; needs_review evaluated as a prediction
- Tests: malformed output, missing text, ambiguous labels, temporary API failure, injected instruction in a synthetic review, deliberately wrong label, interrupted run. Mark synthetic tests and exclude them from business aggregates.

## Saved outputs
- data_manifest.json, ingestion_report.json, enriched.jsonl, quarantine.jsonl
- evals/ (golden labels, predictions, per-field results, verifier results, planted-error and injection cases, recovery evidence)
- issues.csv, aggregates.csv, ranking.csv
- run_log.jsonl, run_summary.json (timing, statuses, attempts, usage, charges, limits, resume evidence)
- cost/, memo.md
- grading/: run.json, ingestion.json, records.jsonl, membership.csv, ranking.csv, claims.csv, calls.jsonl, checkpoint_before.json, checkpoint_after.json (exact format in GRADING_CONTRACT.md; gzip allowed)
- Interruption/resume recording plus checkpoint snapshots

## Deployed system (required)
- Database storing processed reviews, aggregates and analysis outputs
- Deployed backend that reads from the database and serves the dashboard
- Deployed dashboard: overall metrics, issue rankings, AI-generated recommendations with supporting numbers and traceable issue/review evidence
- Live URL and access instructions in the README; grader must inspect results without paid calls

## README must include
- Rubric-to-evidence map
- Results summary: source/completed/quarantined counts, cache reuse, golden agreement, verifier disagreements, full-run cost/time; measured vs estimated kept separate
- Architecture diagram: six stages, code/model boundaries, role inputs/outputs, artifacts, stop/retry paths, database-backend-dashboard
- One real review traced end to end, plus one failed or ambiguous case
- Golden comparison, verifier procedure, injection/planted-error outcomes, resume evidence
- Ranking rules, tie-break, scope; optional trend analysis with denominators (first and last months are partial)
- Memo summary citing claims.csv IDs; limitations (self-selected historical reviews; no revenue, churn or causal claims)
- Setup, run commands, dependency versions, dataset link and checksum

## Rubric (10 points)
- Deliverable quality (4): accessible code/setup; clear architecture, schema, provenance; memo numbers linked to calculations; coherent recommendation, alternatives, limitations
- Testing and evaluation (3): golden 50 with per-field error analysis; independent verification plus planted-error and injection tests; real cold/warm pilot, correct calculator, retry/spend/recovery controls
- Working result (3): full ingestion and classification coverage (formula: 0.2 profile match + 0.2 accounted rows/660,622 + 0.6 classified/660,609); staged program with bounded calls, saved handoffs, demonstrated resume; reproducible ranking plus deployed dashboard with grounded recommendations
- Full corpus required for full credit; "at least 100,000" is the stated floor. Simulated outputs or small demos do not count as the full run.

## Milestones
- Class 7: labels with examples, hand-labeled golden 50, completed 500-review run, eval results, working calculator with measured 100-review cost/time and full-run estimates, offline replay command
- Final (Oct 20): everything above
