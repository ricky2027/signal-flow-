BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE demo_sessions (
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (token_hash)
);

CREATE TABLE quotas (
    key VARCHAR(200) NOT NULL, 
    count INTEGER NOT NULL, 
    PRIMARY KEY (key)
);

CREATE TABLE prospects (
    session_id VARCHAR(36) NOT NULL, 
    data JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES demo_sessions (id)
);

CREATE INDEX ix_prospects_session_id ON prospects (session_id);

CREATE TABLE runs (
    session_id VARCHAR(36) NOT NULL, 
    prospect_id VARCHAR(36) NOT NULL, 
    parent_run_id VARCHAR(36), 
    input JSONB NOT NULL, 
    status VARCHAR(40) NOT NULL, 
    stage VARCHAR(40), 
    outcome_reason VARCHAR(200), 
    warnings JSONB NOT NULL, 
    error JSONB, 
    policy_version VARCHAR(50) NOT NULL, 
    model_versions JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    event_sequence INTEGER NOT NULL, 
    current_draft_id VARCHAR(36), 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(parent_run_id) REFERENCES runs (id), 
    FOREIGN KEY(prospect_id) REFERENCES prospects (id), 
    FOREIGN KEY(session_id) REFERENCES demo_sessions (id)
);

CREATE INDEX ix_runs_session_id ON runs (session_id);

CREATE INDEX ix_runs_status ON runs (status);

CREATE TABLE artifacts (
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(40) NOT NULL, 
    data JSONB NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    UNIQUE (run_id, kind, id)
);

CREATE INDEX ix_artifacts_run_id ON artifacts (run_id);

CREATE TABLE claims (
    run_id VARCHAR(36) NOT NULL, 
    claim_key VARCHAR(100) NOT NULL, 
    data JSONB NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    UNIQUE (run_id, claim_key)
);

CREATE INDEX ix_claims_run_id ON claims (run_id);

CREATE TABLE drafts (
    run_id VARCHAR(36) NOT NULL, 
    version INTEGER NOT NULL, 
    data JSONB NOT NULL, 
    validation_status VARCHAR(20) NOT NULL, 
    validation_findings JSONB NOT NULL, 
    origin VARCHAR(20) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    UNIQUE (run_id, version)
);

CREATE INDEX ix_drafts_run_id ON drafts (run_id);

CREATE TABLE idempotency (
    session_id VARCHAR(36) NOT NULL, 
    key VARCHAR(200) NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    FOREIGN KEY(session_id) REFERENCES demo_sessions (id), 
    UNIQUE (session_id, key)
);

CREATE TABLE jobs (
    run_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    lease_owner VARCHAR(36), 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    instructions VARCHAR(1000), 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id)
);

CREATE INDEX ix_jobs_run_id ON jobs (run_id);

CREATE INDEX ix_jobs_status ON jobs (status);

CREATE UNIQUE INDEX one_active_job ON jobs (run_id) WHERE status IN ('queued', 'leased');

CREATE TABLE provider_calls (
    run_id VARCHAR(36) NOT NULL, 
    data JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id)
);

CREATE INDEX ix_provider_calls_run_id ON provider_calls (run_id);

CREATE TABLE run_events (
    run_id VARCHAR(36) NOT NULL, 
    sequence INTEGER NOT NULL, 
    type VARCHAR(50) NOT NULL, 
    stage VARCHAR(40), 
    payload JSONB NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    UNIQUE (run_id, sequence)
);

CREATE INDEX ix_run_events_run_id ON run_events (run_id);

CREATE TABLE signals (
    run_id VARCHAR(36) NOT NULL, 
    data JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id)
);

CREATE INDEX ix_signals_run_id ON signals (run_id);

CREATE TABLE sources (
    run_id VARCHAR(36) NOT NULL, 
    source_key VARCHAR(100) NOT NULL, 
    url VARCHAR(2048) NOT NULL, 
    data JSONB NOT NULL, 
    retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    UNIQUE (run_id, source_key), 
    UNIQUE (run_id, url)
);

CREATE INDEX ix_sources_run_id ON sources (run_id);

CREATE TABLE claim_sources (
    claim_id VARCHAR(36) NOT NULL, 
    source_id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (claim_id, source_id), 
    FOREIGN KEY(claim_id) REFERENCES claims (id), 
    FOREIGN KEY(source_id) REFERENCES sources (id)
);

CREATE TABLE reviews (
    run_id VARCHAR(36) NOT NULL, 
    draft_id VARCHAR(36) NOT NULL, 
    session_id VARCHAR(36) NOT NULL, 
    action VARCHAR(20) NOT NULL, 
    reason VARCHAR(1000), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(draft_id) REFERENCES drafts (id), 
    FOREIGN KEY(run_id) REFERENCES runs (id), 
    FOREIGN KEY(session_id) REFERENCES demo_sessions (id)
);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

