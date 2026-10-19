# Golden-set evaluation rules (predeclared)

Declared on Oct 19, 2026, before the golden evaluation was run. File: `golden_50_labeled.csv`.

## Label provenance
- Topic, intent and severity: hand-labeled by Natalie, then revised against GRADING_CONTRACT.md rules with Claude's help. Each revision is explained in the `notes` column.
- Sentiment, entities, evidence_quote and needs_review: drafted by Claude (an assistant not used as a pipeline model), then reviewed and confirmed by Natalie. The `drafted_by_claude` column records which fields were drafted.
- Golden labels are never used in prompts, examples, routing thresholds or issue discovery.
- Ambiguous cases: 11 of 50, marked in the `ambiguous` column with the reason in `notes`. None are dropped from scoring.

## Topic, intent, severity
- Report exact agreement for topic and intent, severity exact agreement and mean absolute error, per-topic counts, and a topic confusion table.

## Sentiment
- Five levels: -1, -0.5, 0, 0.5, 1 (matches the Jev mapping sentiment = score / 2 - 1).
  - -1 strongly negative wording (hate, worst, pathetic); -0.5 mild or mixed-negative; 0 neutral or unreadable;
    0.5 mild positive ("good"); 1 strong positive (love, great, excellent).
- Labeled from the review text only, never from star ratings.
- Report mean absolute error, and the share of rows within a tolerance of +/-0.5 (one level).

## Evidence quote
- Check 1 (code): the model's quote is an exact substring of the source text. Pass/fail per row.
- Check 2 (human): the model's quote supports the topic and intent the model chose. Yes/no per row.
- Report both rates. Human quotes are a reference for check 2, not a string-match target.

## Entities
- An entity is a product feature named literally in the review text (for example "ads", "lyrics", "shuffle", "offline mode"). General praise such as "Great app" has no entities.
- Unsupported addition: a model entity that does not appear in the review text (case-insensitive). Report the count and the rate per predicted entity.
- Also report human entities the model missed.

## needs_review
- Scored as a yes/no prediction against the human column: 2x2 table, precision and recall.
- Also report: of rows where the model's topic or intent is wrong, the share the model flagged for review.

## Caveat
Fifty cases are a small diagnostic sample, not a precise estimate of population accuracy.
