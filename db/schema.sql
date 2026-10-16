-- Database schema for the Spotify review pipeline (Supabase Postgres).
-- Apply once in the Supabase SQL editor, or with psql using DATABASE_URL from .env.
-- Holds processed results and analysis outputs only. No API keys or raw CSV contents beyond review text.

create table if not exists runs (
    run_id            text primary key,
    created_at        timestamptz not null default now(),
    source_name       text not null,
    source_sha256     text not null,
    code_version      text,
    label_config      text,
    notes             text
);

-- One row per source review ID (completed or quarantined). Keeps the original source row hash.
create table if not exists records (
    run_id            text not null references runs(run_id),
    review_id         text not null,
    source_sha256     text not null,
    status            text not null check (status in ('completed', 'quarantined', 'pending')),
    topic             text check (topic in ('access','usability','playback','downloads','catalog','billing','support','other')),
    intent            text check (intent in ('cancellation','complaint','request','praise','unclear')),
    sentiment         numeric check (sentiment between -1 and 1),
    severity          integer check (severity between 1 and 5),
    entities          jsonb not null default '[]'::jsonb,
    evidence_quote    text,
    needs_review      boolean,
    cancel_probability numeric check (cancel_probability between 0 and 1),
    label_config      text,
    cache_source_id   text,
    reason            text,
    primary key (run_id, review_id)
);

create table if not exists membership (
    run_id            text not null references runs(run_id),
    issue_id          text not null,
    review_id         text not null,
    primary key (run_id, issue_id, review_id)
);

create table if not exists ranking (
    run_id            text not null references runs(run_id),
    rank              integer not null,
    issue_id          text not null,
    complaint_count   integer not null,
    severity_sum      integer not null,
    mean_severity     numeric(10,6) not null,
    priority_score    integer not null,
    primary key (run_id, issue_id)
);

create table if not exists claims (
    run_id            text not null references runs(run_id),
    claim_id          text not null,
    issue_id          text not null,
    metric            text not null,
    value             text not null,
    primary key (run_id, claim_id)
);

create table if not exists calls (
    run_id            text not null references runs(run_id),
    call_seq          bigint generated always as identity,
    role              text not null check (role in ('classify','enrich','verify','group','memo')),
    model             text,
    phase             text,
    outcome           text not null check (outcome in ('succeeded','failed')),
    status            integer,
    input_tokens      integer,
    output_tokens     integer,
    review_ids        jsonb not null default '[]'::jsonb,
    primary key (run_id, call_seq)
);

-- Read-only views the backend uses. They compute nothing new: they read saved tables.
create or replace view issue_summary as
    select r.run_id, r.issue_id, r.complaint_count, r.severity_sum, r.mean_severity, r.priority_score, r.rank
    from ranking r;

create or replace view status_counts as
    select run_id, status, count(*) as n from records group by run_id, status;
