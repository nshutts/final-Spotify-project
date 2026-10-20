-- Database schema for the deployed dashboard (Supabase Postgres).
-- Apply once: Supabase dashboard -> SQL Editor -> paste this file -> Run.
-- Holds processed results and analysis outputs from a finished run. No API keys.
-- Row-level security allows public READ only; writes need the service-role key (loader only).

drop table if exists reviews, issues, claims, evidence, metrics, monthly cascade;

-- One row per source review ID (completed or quarantined), as exported in grading/records.jsonl.
create table reviews (
    review_id        text primary key,
    source_sha256    text not null,
    status           text not null check (status in ('completed', 'quarantined')),
    reason           text,
    topic            text check (topic in ('access','usability','playback','downloads','catalog','billing','support','other')),
    intent           text check (intent in ('cancellation','complaint','request','praise','unclear')),
    severity         smallint check (severity between 1 and 5),
    sentiment        real check (sentiment between -1 and 1),
    needs_review     boolean,
    evidence_quote   text,
    cache_source_id  text,
    issue_id         text,
    review_rating    smallint,
    review_timestamp text
);
create index reviews_issue_idx on reviews (issue_id, severity desc);

-- Baseline ranking plus the group role's issue names.
create table issues (
    issue_id         text primary key,
    rank             integer not null,
    name             text,
    complaint_count  integer not null,
    severity_sum     integer not null,
    mean_severity    text not null,
    priority_score   integer not null
);

-- claims.csv: every issue-level number the memo cites.
create table claims (
    claim_id  text primary key,
    issue_id  text not null,
    metric    text not null,
    value     text not null
);

-- Bounded evidence packs used by the group and memo roles.
create table evidence (
    issue_id   text not null,
    review_id  text not null,
    severity   smallint,
    quote      text,
    primary key (issue_id, review_id)
);

-- Complaint counts per issue per month (for the trend view; first and last months are partial).
create table monthly (
    month       text not null,
    issue_id    text not null,
    complaints  integer not null,
    reviews     integer not null,
    primary key (month, issue_id)
);

-- Key/value documents: overall metrics, memo decision and text, verifier and golden results, run summary.
create table metrics (
    key    text primary key,
    value  jsonb not null
);

alter table reviews  enable row level security;
alter table issues   enable row level security;
alter table claims   enable row level security;
alter table evidence enable row level security;
alter table monthly  enable row level security;
alter table metrics  enable row level security;
create policy public_read on reviews  for select using (true);
create policy public_read on issues   for select using (true);
create policy public_read on claims   for select using (true);
create policy public_read on evidence for select using (true);
create policy public_read on monthly  for select using (true);
create policy public_read on metrics  for select using (true);
